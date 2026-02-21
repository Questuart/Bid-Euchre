"""
Bidding policy interface and related types for Bid Euchre auction mode.

This module provides the canonical interface for bidding in auction games,
where players bid simultaneously for the right to choose contract and trump.
"""

import json
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from scipy.stats import norm

from ..core.cards import Card
from ..models.bidding_artifact import load_artifact


@dataclass(frozen=True)
class BidAction:
    """
    Represents a bidding action in auction mode.

    Either a pass (n=0) or a bid for n tricks with a specific contract.
    For suit contracts, trump_suit must be specified.
    """

    n: int  # 0 = pass, 1-10 = bid amount
    contract: Optional[str] = None  # contract type or None for passes
    trump_suit: Optional[str] = None  # trump suit for "suit" contracts

    def __post_init__(self):
        """Validate bid action constraints."""
        if self.n < 0 or self.n > 10:
            raise ValueError(f"Bid amount n must be 0-10, got {self.n}")

        if self.n == 0:
            # Pass: contract and trump must be None
            if self.contract is not None:
                raise ValueError(
                    f"Pass (n=0) must have contract=None, got {self.contract}"
                )
            if self.trump_suit is not None:
                raise ValueError(
                    f"Pass (n=0) must have trump_suit=None, got {self.trump_suit}"
                )
        else:
            # Bid: contract must be specified and valid
            if self.contract is None:
                raise ValueError(f"Bid (n={self.n}) must specify contract")
            if self.contract not in {"C", "D", "H", "S", "HIGH", "LOW"}:
                raise ValueError(
                    f"Contract must be one of 'C', 'D', 'H', 'S', 'HIGH', 'LOW', got '{self.contract}'"
                )

            # For suit contracts (C, D, H, S), trump_suit should be None (contract IS the suit)
            # For HIGH/LOW, trump_suit must be None
            if self.trump_suit is not None:
                raise ValueError(
                    f"trump_suit must be None for v1 contracts, got {self.trump_suit}"
                )

    @classmethod
    def pass_bid(cls) -> "BidAction":
        """Create a pass action."""
        return cls(n=0, contract=None, trump_suit=None)

    @classmethod
    def bid(cls, n: int, contract: str) -> "BidAction":
        """Create a bid action."""
        return cls(n=n, contract=contract, trump_suit=None)

    def is_pass(self) -> bool:
        """Return True if this is a pass."""
        return self.n == 0

    def to_contract_tuple(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Convert to the legacy (contract_type, trump_suit) tuple format.

        Returns:
            (contract_type, trump_suit) where:
            - For suit contracts (C, D, H, S): ("suit", contract)
            - For HIGH: ("high", None)
            - For LOW: ("low", None)
            - For pass: (None, None)
        """
        if self.is_pass():
            return None, None
        elif self.contract in {"C", "D", "H", "S"}:
            return "suit", self.contract
        elif self.contract == "HIGH":
            return "high", None
        elif self.contract == "LOW":
            return "low", None
        else:
            raise ValueError(f"Unknown contract: {self.contract}")


@dataclass(frozen=True)
class BiddingObservation:
    """
    Observation provided to bidding policies in auction mode (v1).

    Contains minimal information needed for bidding decisions.
    """

    hand: List[Card]  # Player's current hand
    seat: int  # Player's seat index (0-3)
    dealer_seat: int  # Dealer's seat index (0-3)
    current_high_bid: int  # Current highest bid (0-10, 0 means no bids yet)
    allowed_contracts: Tuple[str, ...] = (
        "C",
        "D",
        "H",
        "S",
        "HIGH",
        "LOW",
    )  # Allowed contract types


class BiddingPolicy(ABC):
    """
    Abstract base class for bidding policies in auction mode.

    Bidding policies decide how to bid based on the current auction state.
    """

    def __init__(self, name: str = "unnamed"):
        self.name = name

    @abstractmethod
    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        """
        Choose a bid action given the current bidding observation.

        Args:
            obs: Current bidding observation

        Returns:
            BidAction to take (pass or bid with contract)
        """
        pass

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.name})"

    def __repr__(self) -> str:
        return str(self)


class AlwaysPassBidder(BiddingPolicy):
    """
    Baseline bidder that always passes (n=0).
    """

    def __init__(self, name: str = "always_pass"):
        super().__init__(name)

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        return BidAction.pass_bid()


class StrictHellRaiser(BiddingPolicy):
    """
    Baseline bidder that follows strict raising rules.

    - If current_high_bid == 0: bid 3
    - If current_high_bid < 10: bid current_high_bid + 1
    - If current_high_bid >= 10: pass
    - Always bids for "S" (Spades) contract (deterministic choice)
    """

    def __init__(self, name: str = "strict_raiser"):
        super().__init__(name)

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        current = obs.current_high_bid

        if current == 0:
            return BidAction.bid(3, "S")
        elif current < 10:
            return BidAction.bid(current + 1, "S")
        else:
            # current >= 10, cannot raise further
            return BidAction.pass_bid()


# Backward-compatibility alias
StrictRaiserBidder = StrictHellRaiser


class FixedBidder(BiddingPolicy):
    """
    Baseline bidder that bids a fixed amount and contract.

    If the fixed bid is higher than current_high_bid, bids it.
    Otherwise, passes.
    """

    def __init__(self, n: int, contract: str, name: str = "fixed_bidder"):
        super().__init__(name)
        if n < 1 or n > 10:
            raise ValueError(f"Fixed bid n must be 1-10, got {n}")
        if contract not in {"C", "D", "H", "S", "HIGH", "LOW"}:
            raise ValueError(f"Invalid contract: {contract}")
        self.n = n
        self.contract = contract

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        if self.n > obs.current_high_bid:
            return BidAction.bid(self.n, self.contract)
        else:
            return BidAction.pass_bid()


class HeuristicSuitBidder(BiddingPolicy):
    """
    Heuristic bidder that uses hand strength to choose suit contract.

    - Evaluates hand strength for each suit (C, D, H, S)
    - Picks the strongest suit deterministically
    - Bids based on strength thresholds:
      - strength >= 350: bid 6
      - strength >= 300: bid 5
      - strength >= 250: bid 4
      - strength >= 200: bid 3
      - else: pass
    - Complies with strict-increasing rule (only bids if > current_high_bid)
    """

    def __init__(self, name: str = "heuristic_suit"):
        super().__init__(name)

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        from ..features.hand_eval import score_hand_scalar

        # Evaluate hand strength for each suit
        suit_scores = {}
        for suit in ["C", "D", "H", "S"]:
            suit_scores[suit] = score_hand_scalar(obs.hand, "suit", suit)

        # Pick strongest suit deterministically (ties broken alphabetically)
        best_suit = max(suit_scores, key=lambda s: (suit_scores[s], s))
        strength = suit_scores[best_suit]

        # Determine bid amount based on strength thresholds
        if strength >= 350:
            bid_n = 6
        elif strength >= 300:
            bid_n = 5
        elif strength >= 250:
            bid_n = 4
        elif strength >= 200:
            bid_n = 3
        else:
            # Too weak, pass
            return BidAction.pass_bid()

        # Comply with strict-increasing rule
        if bid_n > obs.current_high_bid:
            return BidAction.bid(bid_n, best_suit)
        else:
            return BidAction.pass_bid()


class HighLowHeuristicBidder(BiddingPolicy):
    """
    Heuristic bidder that chooses HIGH or LOW based on hand composition.

    - Counts high cards (A, K, Q) vs low cards (J, T)
    - If more high cards: bid HIGH
    - If more low cards: bid LOW
    - Ties: bid HIGH (deterministic)
    - Bid amount based on strength:
      - strength >= 40: bid 5
      - strength >= 30: bid 4
      - strength >= 20: bid 3
      - else: pass
    - Complies with strict-increasing rule
    """

    def __init__(self, name: str = "high_low_heuristic"):
        super().__init__(name)

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        from ..features.hand_eval import score_hand_scalar

        # Count high vs low cards
        high_cards = sum(1 for card in obs.hand if card.rank in {"A", "K", "Q"})
        low_cards = sum(1 for card in obs.hand if card.rank in {"J", "T"})

        # Choose contract (HIGH if tied or more high cards)
        if high_cards >= low_cards:
            contract = "HIGH"
            strength = score_hand_scalar(obs.hand, "high", None)
        else:
            contract = "LOW"
            strength = score_hand_scalar(obs.hand, "low", None)

        # Determine bid amount based on strength
        if strength >= 40:
            bid_n = 5
        elif strength >= 30:
            bid_n = 4
        elif strength >= 20:
            bid_n = 3
        else:
            return BidAction.pass_bid()

        # Comply with strict-increasing rule
        if bid_n > obs.current_high_bid:
            return BidAction.bid(bid_n, contract)
        else:
            return BidAction.pass_bid()


class RanktheTank(BiddingPolicy):
    """
    Rank-sum based bidder (v1 baseline) that evaluates all contract options.

    This is the v1 baseline bidder that combines suit and HIGH/LOW evaluation:
    - Evaluates hand strength for all suit contracts (C, D, H, S)
    - Evaluates HIGH/LOW contracts based on hand composition
    - Maps strength to bid via thresholds (350→6, 300→5, 250→4, 200→3)
    - Complies with strict-increasing bid rule

    Named after the blog post character who bids based on "my hand looks big."
    Serves as the canonical "rankthetank" teacher for imitation learning.
    """

    def __init__(self, name: str = "rankthetank"):
        super().__init__(name)

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        from ..features.hand_eval import score_hand_scalar

        # Evaluate all contract options
        candidates = []

        # Evaluate suit contracts
        for suit in ["C", "D", "H", "S"]:
            strength = score_hand_scalar(obs.hand, "suit", suit)

            # Map strength to bid amount using HeuristicSuitBidder thresholds
            if strength >= 350:
                bid_n = 6
            elif strength >= 300:
                bid_n = 5
            elif strength >= 250:
                bid_n = 4
            elif strength >= 200:
                bid_n = 3
            else:
                continue  # Too weak, skip this contract

            # Check strict-increasing rule
            if bid_n > obs.current_high_bid:
                candidates.append((strength, bid_n, suit))

        # Evaluate HIGH/LOW contracts
        high_cards = sum(1 for card in obs.hand if card.rank in {"A", "K", "Q"})
        low_cards = sum(1 for card in obs.hand if card.rank in {"J", "T"})

        # HIGH contract
        if high_cards >= low_cards:
            strength_high = score_hand_scalar(obs.hand, "high", None)
            if strength_high >= 40:
                bid_n = 5
            elif strength_high >= 30:
                bid_n = 4
            elif strength_high >= 20:
                bid_n = 3
            else:
                bid_n = 0

            if bid_n > obs.current_high_bid:
                candidates.append((strength_high, bid_n, "HIGH"))

        # LOW contract
        if low_cards > high_cards:
            strength_low = score_hand_scalar(obs.hand, "low", None)
            if strength_low >= 40:
                bid_n = 5
            elif strength_low >= 30:
                bid_n = 4
            elif strength_low >= 20:
                bid_n = 3
            else:
                bid_n = 0

            if bid_n > obs.current_high_bid:
                candidates.append((strength_low, bid_n, "LOW"))

        # No valid candidates
        if not candidates:
            return BidAction.pass_bid()

        # Pick best candidate (highest strength, break ties by highest bid, then alphabetically)
        best = max(candidates, key=lambda x: (x[0], x[1], x[2]))
        _, bid_n, contract = best

        return BidAction.bid(bid_n, contract)


class ModeloEspecifico(BiddingPolicy):
    """
    Feature-weighted bidder using hand-coded weights.

    Formulas (locked):
      suit: 1.0 * bowers + 0.5 * trump_count + 0.5 * offsuit_aces
      HIGH: 1.0 * offsuit_aces
      LOW:  1.0 * offsuit_tens_count

    The score maps directly to bid amount (floored).
    Named after the blog post's "specific model" baseline.
    """

    def __init__(self, name: str = "modelo_especifico"):
        super().__init__(name)

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        from ..features.hand_eval import get_hand_features

        candidates = []

        # Evaluate suit contracts
        for suit in ["C", "D", "H", "S"]:
            features = get_hand_features(obs.hand, "suit", suit)
            score = (
                1.0 * features["bowers"]
                + 0.5 * features["trump_count"]
                + 0.5 * features["offsuit_aces"]
            )
            bid_n = int(score)  # floor
            if 3 <= bid_n <= 6 and bid_n > obs.current_high_bid:
                candidates.append((score, bid_n, suit))

        # Evaluate HIGH contract: score = 1.0 * offsuit_aces
        features_high = get_hand_features(obs.hand, "high", None)
        score_high = 1.0 * features_high["offsuit_aces"]
        bid_n_high = int(score_high)
        if 3 <= bid_n_high <= 6 and bid_n_high > obs.current_high_bid:
            candidates.append((score_high, bid_n_high, "HIGH"))

        # Evaluate LOW contract: score = 1.0 * offsuit_tens_count
        features_low = get_hand_features(obs.hand, "low", None)
        score_low = 1.0 * features_low["offsuit_tens_count"]
        bid_n_low = int(score_low)
        if 3 <= bid_n_low <= 6 and bid_n_low > obs.current_high_bid:
            candidates.append((score_low, bid_n_low, "LOW"))

        if not candidates:
            return BidAction.pass_bid()

        # Pick best: highest score, break ties by bid amount, then alphabetically
        best = max(candidates, key=lambda x: (x[0], x[1], x[2]))
        return BidAction.bid(best[1], best[2])


class ArtifactBidder(BiddingPolicy):
    """
    Bidding policy that loads and executes a trained model from a bidding artifact file.

    Supports multiple model types:
    - 'linear_regression': Linear model with hand features
    - 'strict_raiser_imitation_v1': Rule-based model replicating StrictRaiserBidder
    - 'heuristics_imitation_v1': Rule-based model replicating RanktheTank

    The artifact is loaded and validated at initialization time.
    """

    def __init__(self, artifact_path: str, name: str = None):
        """
        Initialize bidder from artifact file.

        Args:
            artifact_path: Path to JSON bidding artifact file
            name: Optional name for this bidder (defaults to artifact contract)

        Raises:
            FileNotFoundError: If artifact file doesn't exist
            ValueError: If artifact is invalid or unsupported
        """
        # Load and validate artifact
        try:
            self.artifact = load_artifact(artifact_path)
        except FileNotFoundError:
            raise FileNotFoundError(f"Bidding artifact not found: {artifact_path}")
        except ValueError as e:
            raise ValueError(f"Invalid bidding artifact at {artifact_path}: {e}")

        # Set name
        if name is None:
            name = f"artifact_{self.artifact['contract']}"

        super().__init__(name)

        # Initialize model-specific state
        self.model_type = self.artifact["model_type"]
        if self.model_type == "linear_regression":
            raise NotImplementedError(
                "linear_regression artifacts are reserved for future work. This runtime path is not implemented and would silently pass. "
                "Use strict_raiser_imitation_v1 or heuristics_imitation_v1 instead."
            )
        elif self.model_type == "strict_raiser_imitation_v1":
            self._init_strict_raiser_imitation()
        elif self.model_type == "heuristics_imitation_v1":
            self._init_heuristics_imitation()
        else:
            raise ValueError(
                f"Unsupported model_type '{self.model_type}' in artifact {artifact_path}"
            )

    def _init_linear_regression(self):
        """Initialize linear regression model parameters."""
        params = self.artifact["model_params"]
        required_keys = {"coefficients", "intercept"}
        if not required_keys.issubset(params.keys()):
            raise ValueError(
                f"Linear regression model missing required parameters: {required_keys - set(params.keys())}"
            )

        self.coefficients = params["coefficients"]
        self.intercept = params["intercept"]

        # Optional: feature names for validation/debugging
        self.feature_names = params.get("features", [])

        # Validate coefficients is a list/array-like
        if not isinstance(self.coefficients, list):
            raise ValueError("Linear regression coefficients must be a list")

    def _init_strict_raiser_imitation(self):
        """Initialize strict raiser imitation model parameters."""
        params = self.artifact["model_params"]
        required_keys = {"initial_bid", "raise_increment", "max_bid", "contract"}
        if not required_keys.issubset(params.keys()):
            raise ValueError(
                f"Strict raiser imitation model missing required parameters: {required_keys - set(params.keys())}"
            )

        self.rules = params

    def _init_heuristics_imitation(self):
        """Initialize heuristics imitation model parameters."""
        params = self.artifact["model_params"]
        required_keys = {
            "suit_thresholds",
            "high_low_thresholds",
            "high_card_ranks",
            "low_card_ranks",
        }
        if not required_keys.issubset(params.keys()):
            raise ValueError(
                f"Heuristics imitation model missing required parameters: {required_keys - set(params.keys())}"
            )

        self.rules = params

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        """
        Choose a bid action using the loaded model.

        Args:
            obs: Current bidding observation

        Returns:
            BidAction to take
        """
        if self.model_type == "linear_regression":
            return self._choose_bid_linear(obs)
        elif self.model_type == "strict_raiser_imitation_v1":
            return self._choose_bid_strict_raiser(obs)
        elif self.model_type == "heuristics_imitation_v1":
            return self._choose_bid_heuristics(obs)
        else:
            # Should never happen due to validation in __init__
            raise ValueError(f"Unsupported model type: {self.model_type}")

    def _choose_bid_linear(self, obs: BiddingObservation) -> BidAction:
        """Choose bid using linear regression model (not yet implemented)."""
        raise NotImplementedError(
            "linear_regression bidding is not yet implemented. "
            "Use strict_raiser_imitation_v1 or heuristics_imitation_v1."
        )

    def _choose_bid_strict_raiser(self, obs: BiddingObservation) -> BidAction:
        """Choose bid using strict raiser imitation model."""
        current = obs.current_high_bid

        if current == 0:
            return BidAction.bid(
                self.rules["initial_bid"]["n"], self.rules["initial_bid"]["contract"]
            )
        elif current < self.rules["max_bid"]:
            return BidAction.bid(
                current + self.rules["raise_increment"], self.rules["contract"]
            )
        else:
            # current >= max_bid, cannot raise further
            return BidAction.pass_bid()

    def _choose_bid_heuristics(self, obs: BiddingObservation) -> BidAction:
        """Choose bid using heuristics imitation model."""
        from ..features.hand_eval import score_hand_scalar

        # Evaluate all contract options
        candidates = []

        # Evaluate suit contracts
        for suit in ["C", "D", "H", "S"]:
            strength = score_hand_scalar(obs.hand, "suit", suit)

            # Map strength to bid amount
            if strength >= self.rules["suit_thresholds"]["bid_6"]:
                bid_n = 6
            elif strength >= self.rules["suit_thresholds"]["bid_5"]:
                bid_n = 5
            elif strength >= self.rules["suit_thresholds"]["bid_4"]:
                bid_n = 4
            elif strength >= self.rules["suit_thresholds"]["bid_3"]:
                bid_n = 3
            else:
                continue  # Too weak

            if bid_n > obs.current_high_bid:
                candidates.append((strength, bid_n, suit))

        # Evaluate HIGH/LOW contracts
        high_cards = sum(
            1 for card in obs.hand if card.rank in self.rules["high_card_ranks"]
        )
        low_cards = sum(
            1 for card in obs.hand if card.rank in self.rules["low_card_ranks"]
        )

        # HIGH contract
        if high_cards >= low_cards:
            strength_high = score_hand_scalar(obs.hand, "high", None)
            if strength_high >= self.rules["high_low_thresholds"]["bid_5"]:
                bid_n = 5
            elif strength_high >= self.rules["high_low_thresholds"]["bid_4"]:
                bid_n = 4
            elif strength_high >= self.rules["high_low_thresholds"]["bid_3"]:
                bid_n = 3
            else:
                bid_n = 0

            if bid_n > obs.current_high_bid:
                candidates.append((strength_high, bid_n, "HIGH"))

        # LOW contract
        if low_cards > high_cards:
            strength_low = score_hand_scalar(obs.hand, "low", None)
            if strength_low >= self.rules["high_low_thresholds"]["bid_5"]:
                bid_n = 5
            elif strength_low >= self.rules["high_low_thresholds"]["bid_4"]:
                bid_n = 4
            elif strength_low >= self.rules["high_low_thresholds"]["bid_3"]:
                bid_n = 3
            else:
                bid_n = 0

            if bid_n > obs.current_high_bid:
                candidates.append((strength_low, bid_n, "LOW"))

        # No valid candidates
        if not candidates:
            return BidAction.pass_bid()

        # Pick best candidate (highest strength, break ties by highest bid, then alphabetically)
        best = max(candidates, key=lambda x: (x[0], x[1], x[2]))
        _, bid_n, contract = best

        return BidAction.bid(bid_n, contract)


class OLSaBidder(BiddingPolicy):
    """
    OLSa bidder: per-contract sparse OLS predicting tricks_won.

    Evaluates all 6 contracts (4 suits + HIGH + LOW), predicts tricks for
    each using the corresponding sparse OLS model, floors to get bid amount,
    and picks the best candidate.

    Artifact format: olsa_v1.json with models for "suit", "high", "low".
    """

    def __init__(self, artifact_path: str, name: str = "olsa"):
        super().__init__(name)

        with open(artifact_path) as f:
            artifact = json.load(f)

        if artifact.get("artifact_type") != "olsa_v1":
            raise ValueError(
                f"Expected artifact_type 'olsa_v1', got '{artifact.get('artifact_type')}'"
            )

        self.models = {}
        for contract_family, model_data in artifact["models"].items():
            self.models[contract_family] = {
                "weights": np.array(model_data["weights"], dtype=np.float64),
                "bias": float(model_data["bias"]),
                "feature_names": model_data["feature_names"],
            }

    def _predict(self, contract_family: str, features: dict) -> float:
        """Predict tricks_won for a contract family using its OLS model."""
        model = self.models[contract_family]
        x = np.array([features[f] for f in model["feature_names"]], dtype=np.float64)
        return float(x @ model["weights"] + model["bias"])

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        from ..features.hand_eval import get_hand_features

        candidates = []

        # Evaluate suit contracts (4 suits, one model)
        if "suit" in self.models:
            for suit in ["C", "D", "H", "S"]:
                features = get_hand_features(obs.hand, "suit", suit)
                predicted_tricks = self._predict("suit", features)
                bid_n = math.floor(predicted_tricks)
                if 3 <= bid_n <= 10 and bid_n > obs.current_high_bid:
                    candidates.append((predicted_tricks, bid_n, suit))

        # Evaluate HIGH
        if "high" in self.models:
            features = get_hand_features(obs.hand, "high", None)
            predicted_tricks = self._predict("high", features)
            bid_n = math.floor(predicted_tricks)
            if 3 <= bid_n <= 10 and bid_n > obs.current_high_bid:
                candidates.append((predicted_tricks, bid_n, "HIGH"))

        # Evaluate LOW
        if "low" in self.models:
            features = get_hand_features(obs.hand, "low", None)
            predicted_tricks = self._predict("low", features)
            bid_n = math.floor(predicted_tricks)
            if 3 <= bid_n <= 10 and bid_n > obs.current_high_bid:
                candidates.append((predicted_tricks, bid_n, "LOW"))

        if not candidates:
            return BidAction.pass_bid()

        # Pick best: highest predicted tricks, break ties by bid amount, then alphabetically
        best = max(candidates, key=lambda x: (x[0], x[1], x[2]))
        return BidAction.bid(best[1], best[2])


class HybridOLSaBidder(BiddingPolicy):
    """Hybrid OLSa bidder using Gaussian EV with net-differential scoring.

    For each contract, predicts mu (expected tricks) via OLS, then analytically
    computes expected net-differential value using a Gaussian model of trick
    distribution with residual variance from training.

    Net-differential payoff:
      Make (tricks >= bid_n): net = 2 * tricks - 10
      Set  (tricks < bid_n):  net = tricks - bid_n - 10

    Artifact format: hybrid_olsa_v1 with payoff_model, residual_variance, risk_lambda.
    """

    # z-cap to prevent numerical overflow in CDF/PDF
    _Z_CAP = 6.0
    # Fixed seed and draw count for CVaR Monte Carlo
    _CVAR_SEED = 42
    _CVAR_DRAWS = 1000
    _CVAR_TAIL = 0.05

    def __init__(
        self, artifact_path: str, risk_lambda: float = None, name: str = "hybrid_olsa"
    ):
        super().__init__(name)

        with open(artifact_path) as f:
            artifact = json.load(f)

        if artifact.get("artifact_type") != "hybrid_olsa_v1":
            raise ValueError(
                f"Expected artifact_type 'hybrid_olsa_v1', "
                f"got '{artifact.get('artifact_type')}'"
            )

        # Detect offensive/defensive sub-structure
        self._has_offdef = any(
            "offensive" in model_data
            for model_data in artifact["payoff_model"].values()
        )

        # Validate consistency: if payoff_model has off/def, residual_variance must too
        variance_has_offdef = any(
            isinstance(v, dict) and "offensive" in v
            for v in artifact["residual_variance"].values()
        )
        if self._has_offdef != variance_has_offdef:
            raise ValueError(
                "Inconsistent off/def structure: payoff_model "
                f"{'has' if self._has_offdef else 'lacks'} offensive/defensive keys "
                f"but residual_variance {'has' if variance_has_offdef else 'lacks'} them"
            )

        self.models = {}
        if self._has_offdef:
            # Off/def: nested sub-models per contract family
            for contract_family, model_data in artifact["payoff_model"].items():
                self.models[contract_family] = {}
                for role in ("offensive", "defensive"):
                    sub = model_data[role]
                    self.models[contract_family][role] = {
                        "weights": np.array(sub["weights"], dtype=np.float64),
                        "bias": float(sub["bias"]),
                        "feature_names": sub["feature_names"],
                    }
        else:
            # Flat: original single model per contract family
            for contract_family, model_data in artifact["payoff_model"].items():
                self.models[contract_family] = {
                    "weights": np.array(model_data["weights"], dtype=np.float64),
                    "bias": float(model_data["bias"]),
                    "feature_names": model_data["feature_names"],
                }

        # Residual variance: either flat floats or nested off/def dicts
        if self._has_offdef:
            self.residual_variance = {}
            for cf, v in artifact["residual_variance"].items():
                self.residual_variance[cf] = {
                    "offensive": float(v["offensive"]),
                    "defensive": float(v["defensive"]),
                }
        else:
            self.residual_variance = {
                cf: float(v) for cf, v in artifact["residual_variance"].items()
            }

        # risk_lambda param overrides artifact value if provided
        if risk_lambda is not None:
            self.risk_lambda = float(risk_lambda)
        else:
            self.risk_lambda = float(artifact.get("risk_lambda", 0.0))

        self.context_features = artifact.get("context_features", [])

    def _predict(
        self, contract_family: str, features: dict, *, declaring: bool = True
    ) -> float:
        """Predict tricks_won (mu) for a contract family using its OLS model.

        Args:
            contract_family: One of "suit", "high", "low".
            features: Feature dict from get_hand_features().
            declaring: If True, use offensive model; if False, use defensive.
                Only relevant for off/def artifacts; flat artifacts ignore this.
        """
        if self._has_offdef:
            role = "offensive" if declaring else "defensive"
            model = self.models[contract_family][role]
        else:
            model = self.models[contract_family]
        x = np.array([features[f] for f in model["feature_names"]], dtype=np.float64)
        return float(x @ model["weights"] + model["bias"])

    def _get_sigma(self, contract_family: str, *, declaring: bool = True) -> float:
        """Get residual standard deviation for a contract family.

        Args:
            contract_family: One of "suit", "high", "low".
            declaring: If True, use offensive variance; if False, defensive.
                Only relevant for off/def artifacts; flat artifacts ignore this.

        Returns:
            Standard deviation (sqrt of residual variance).
        """
        if self._has_offdef:
            role = "offensive" if declaring else "defensive"
            var = self.residual_variance[contract_family][role]
        else:
            var = self.residual_variance.get(contract_family, 0.0)
        return math.sqrt(max(0.0, var))

    def _compute_ev(self, mu: float, sigma: float, bid_n: int) -> float:
        """Compute expected net-differential value using Gaussian model.

        Uses analytical truncated normal expectations above/below the make threshold.
        """
        if sigma == 0.0:
            # Degenerate case: deterministic prediction
            if mu >= bid_n:
                return 2.0 * mu - 10.0
            else:
                return mu - bid_n - 10.0

        # Threshold for making the bid (continuous approximation)
        threshold = bid_n - 0.5

        # z-score with capping for numerical stability
        z = (threshold - mu) / sigma
        z = max(-self._Z_CAP, min(self._Z_CAP, z))

        # P(make) = P(tricks >= threshold) = 1 - Phi(z)
        p_make = 1.0 - norm.cdf(z)
        p_set = 1.0 - p_make

        # Truncated normal expectations
        pdf_z = norm.pdf(z)

        # E[X | X >= threshold] = mu + sigma * pdf(z) / (1 - Phi(z))
        if p_make > 1e-12:
            e_tricks_make = mu + sigma * pdf_z / p_make
        else:
            e_tricks_make = mu  # fallback, p_make ~ 0 so doesn't matter

        # E[X | X < threshold] = mu - sigma * pdf(z) / Phi(z)
        if p_set > 1e-12:
            e_tricks_set = mu - sigma * pdf_z / p_set
        else:
            e_tricks_set = mu  # fallback, p_set ~ 0 so doesn't matter

        # Net-differential payoffs
        make_ev = 2.0 * e_tricks_make - 10.0
        set_ev = e_tricks_set - bid_n - 10.0

        return p_make * make_ev + p_set * set_ev

    def _compute_risk_penalty(self, mu: float, sigma: float, bid_n: int) -> float:
        """Compute risk penalty based on CVaR of net-differential distribution.

        Uses Monte Carlo sampling with deterministic seed for reproducibility.
        Returns max(0, -CVaR_5%) * risk_lambda.
        """
        if self.risk_lambda == 0.0:
            return 0.0

        if sigma == 0.0:
            # Deterministic: single outcome
            if mu >= bid_n:
                net = 2.0 * mu - 10.0
            else:
                net = mu - bid_n - 10.0
            cvar = net  # single-point CVaR
            return max(0.0, -cvar) * self.risk_lambda

        rng = np.random.RandomState(self._CVAR_SEED)
        draws = rng.normal(mu, sigma, self._CVAR_DRAWS)

        # Compute net differential for each draw
        nets = np.where(
            draws >= bid_n,
            2.0 * draws - 10.0,
            draws - bid_n - 10.0,
        )

        # CVaR = mean of worst tail_fraction
        tail_size = max(1, int(self._CVAR_DRAWS * self._CVAR_TAIL))
        sorted_nets = np.sort(nets)
        cvar = float(sorted_nets[:tail_size].mean())

        return max(0.0, -cvar) * self.risk_lambda

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        from ..features.hand_eval import get_hand_features

        best_utility = None
        best_bid_n = None
        best_contract = None

        contract_map = {
            "suit": ["C", "D", "H", "S"],
            "high": ["HIGH"],
            "low": ["LOW"],
        }

        for contract_family, contracts in contract_map.items():
            if contract_family not in self.models:
                continue

            sigma = self._get_sigma(contract_family, declaring=True)

            for contract in contracts:
                # Get hand features for this contract
                if contract in ("HIGH", "LOW"):
                    features = get_hand_features(obs.hand, contract_family, None)
                else:
                    features = get_hand_features(obs.hand, "suit", contract)

                mu = self._predict(contract_family, features, declaring=True)
                bid_n = math.floor(mu)

                # Clamp bid to valid range
                if bid_n < 3 or bid_n > 10:
                    continue

                # Must exceed current high bid
                if bid_n <= obs.current_high_bid:
                    continue

                ev = self._compute_ev(mu, sigma, bid_n)
                penalty = self._compute_risk_penalty(mu, sigma, bid_n)
                utility = ev - penalty

                if (
                    best_utility is None
                    or utility > best_utility
                    or (
                        utility == best_utility
                        and (bid_n, contract) > (best_bid_n, best_contract)
                    )
                ):
                    best_utility = utility
                    best_bid_n = bid_n
                    best_contract = contract

        if best_utility is None or best_utility <= 0:
            return BidAction.pass_bid()

        return BidAction.bid(best_bid_n, best_contract)
