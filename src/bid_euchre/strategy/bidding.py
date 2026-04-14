"""
Bidding policy interface and related types for Bid Euchre auction mode.

This module provides the canonical interface for bidding in auction games,
where players bid simultaneously for the right to choose contract and trump.
"""

import hashlib
import json
import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from scipy.stats import norm

from ..core.cards import Card
from ..models.bidding_artifact import load_artifact

logger = logging.getLogger(__name__)

# R² threshold for load-time quality warning. Artifacts with any bid-contract
# model below this threshold trigger a warning — catches wrong-target or stale
# artifacts before gameplay. The stale artifact incident had R²=0.183.
_R2_WARNING_THRESHOLD = 0.30


@dataclass(frozen=True)
class BidAction:
    """
    Represents a bidding action in auction mode.

    Either a pass (n=0) or a bid for n tricks with a specific contract.
    For suit contracts, trump_suit must be specified.

    bid_type controls the auction hierarchy:
    - "regular": Standard bid (levels 1-10)
    - "moon": All 10 tricks, overcalls any regular bid
    - "loner": All 10 tricks solo (partner sits out), overcalls moon
    """

    n: int  # 0 = pass, 1-10 = bid amount
    contract: Optional[str] = None  # contract type or None for passes
    trump_suit: Optional[str] = None  # trump suit for "suit" contracts
    bid_type: str = "regular"  # "regular" | "moon" | "loner"

    # Numeric rank for overcall hierarchy comparisons
    _BID_TYPE_RANK = {"regular": 0, "moon": 1, "loner": 2}

    def __post_init__(self):
        """Validate bid action constraints."""
        if self.n < 0 or self.n > 10:
            raise ValueError(f"Bid amount n must be 0-10, got {self.n}")

        if self.bid_type not in {"regular", "moon", "loner"}:
            raise ValueError(
                f"bid_type must be 'regular', 'moon', or 'loner', got '{self.bid_type}'"
            )

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
            if self.bid_type != "regular":
                raise ValueError(
                    f"Pass (n=0) must have bid_type='regular', got '{self.bid_type}'"
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

            # Moon and loner are always level 10
            if self.bid_type in {"moon", "loner"} and self.n != 10:
                raise ValueError(
                    f"{self.bid_type} bids must be level 10, got n={self.n}"
                )

    @classmethod
    def pass_bid(cls) -> "BidAction":
        """Create a pass action."""
        return cls(n=0, contract=None, trump_suit=None, bid_type="regular")

    @classmethod
    def bid(cls, n: int, contract: str) -> "BidAction":
        """Create a regular bid action."""
        return cls(n=n, contract=contract, trump_suit=None, bid_type="regular")

    @classmethod
    def moon(cls, contract: str) -> "BidAction":
        """Create a moon bid action (always level 10)."""
        return cls(n=10, contract=contract, trump_suit=None, bid_type="moon")

    @classmethod
    def loner(cls, contract: str) -> "BidAction":
        """Create a loner bid action (always level 10)."""
        return cls(n=10, contract=contract, trump_suit=None, bid_type="loner")

    def is_pass(self) -> bool:
        """Return True if this is a pass."""
        return self.n == 0

    def bid_rank(self) -> int:
        """Return numeric rank for overcall comparisons.

        Hierarchy: regular bids by level < moon < loner.
        Pass returns -1 (below all bids).
        """
        if self.is_pass():
            return -1
        type_rank = self._BID_TYPE_RANK[self.bid_type]
        if self.bid_type == "regular":
            # Regular bids ranked by level (1-10)
            return self.n
        else:
            # Moon = 11, Loner = 12 (above any regular bid including 10)
            return 10 + type_rank

    def overcalls(self, other: "BidAction") -> bool:
        """Return True if this bid strictly overcalls the other bid.

        Overcall hierarchy: regular N < regular N+1 < ... < regular 10 < moon < loner.
        A pass never overcalls anything. A bid always overcalls a pass.
        """
        if self.is_pass():
            return False
        if other.is_pass():
            return True
        return self.bid_rank() > other.bid_rank()

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


def enumerate_legal_actions(
    obs: "BiddingObservation",
    *,
    include_moon_loner: bool = False,
    current_bid_type: str = "regular",
    is_dealer: bool = False,
) -> List[BidAction]:
    """Enumerate all legal bidding actions for the current auction state.

    Returns actions in canonical order: PASS first, then ascending by
    (bid_level, contract) where contract order follows obs.allowed_contracts.
    When include_moon_loner=True, moon and loner bids are appended after
    regular bids.

    Args:
        obs: Current bidding observation.
        include_moon_loner: If True, include moon/loner actions when legal.
        current_bid_type: The bid_type of the current high bid
            ("regular", "moon", or "loner"). Only relevant when
            include_moon_loner=True.
        is_dealer: Whether the current player is the dealer. Dealers can
            "take away" (match) a moon or loner bid. Only relevant when
            include_moon_loner=True.

    Used by both ActionValueBidder.choose_bid() and the counterfactual
    dataset generator to ensure consistent action enumeration.
    """
    actions: List[BidAction] = [BidAction.pass_bid()]

    # Regular bids: only legal if current high bid is a regular bid
    if current_bid_type == "regular":
        for n in range(obs.current_high_bid + 1, 11):
            for contract in obs.allowed_contracts:
                actions.append(BidAction.bid(n, contract))

    if include_moon_loner:
        # Moon bids: legal if current high bid is regular (overcalls it)
        # or if dealer is taking away a moon
        if current_bid_type == "regular" or (current_bid_type == "moon" and is_dealer):
            for contract in obs.allowed_contracts:
                actions.append(BidAction.moon(contract))

        # Loner bids: legal if current high bid is regular or moon
        # (overcalls both), or if dealer is taking away a loner
        if current_bid_type in {"regular", "moon"} or (
            current_bid_type == "loner" and is_dealer
        ):
            for contract in obs.allowed_contracts:
                actions.append(BidAction.loner(contract))

    return actions


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
    auction_transcript: Tuple[dict, ...] = ()  # Prior bid actions in auction order
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

    Subclasses should set a ``VERSION`` class attribute (semver string)
    that is bumped on every behavioral change.
    """

    # Default version for policies that have not opted into versioning.
    VERSION: str = "0.0.0"

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

    def fingerprint(self) -> str:
        """Return a short hex digest identifying this policy's version and config.

        Subclasses with extra configuration (artifact paths, thresholds, etc.)
        should override and include those values.

        Returns:
            8-character hex digest (first 8 chars of SHA-256).
        """
        parts = [
            type(self).__name__,
            type(self).VERSION,
            self.name,
        ]
        blob = "|".join(parts).encode()
        return hashlib.sha256(blob).hexdigest()[:8]

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.name})"

    def __repr__(self) -> str:
        return str(self)


# Module-level version constants for bidding policy families.
# Heuristic bidders have been stable since initial commit.
HEURISTIC_BIDDER_VERSION = "1.0.0"
# Artifact-backed bidders derive behavior from the artifact + thin wrapper
# logic. Bump this when the wrapper changes (not when the artifact does).
ARTIFACT_BIDDER_VERSION = "1.0.0"


class AlwaysPassBidder(BiddingPolicy):
    """
    Baseline bidder that always passes (n=0).
    """

    VERSION = HEURISTIC_BIDDER_VERSION

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

    VERSION = HEURISTIC_BIDDER_VERSION

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

    VERSION = HEURISTIC_BIDDER_VERSION

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

    .. note:: Not registered in the experiment config registry — internal only.
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


# ── Derivation: RanktheTank threshold-to-bid mapping ──
# Source: hand-crafted heuristic baseline, not learned from data
# Formula: score_hand_scalar() → ~10-point spacing thresholds → bid_n
#   Suit: 100→1, 150→2, 200→3, 250→4, 300→5, 350→6, 450→7, 550→8, 650→9, 750→10
#   HIGH/LOW: 100→1, 150→2, 200→3, 280→4, 350→5, 400→6, 450→7, 500→8
# Assumptions: score_hand_scalar provides monotonic ordering of hand strength
# See also: score_hand_scalar() in features/hand_eval.py


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

    VERSION = HEURISTIC_BIDDER_VERSION

    def __init__(self, name: str = "rankthetank"):
        super().__init__(name)

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        from ..features.hand_eval import score_hand_scalar

        # Evaluate all contract options
        candidates = []

        # Evaluate suit contracts
        for suit in ["C", "D", "H", "S"]:
            strength = score_hand_scalar(obs.hand, "suit", suit)

            # Map strength to bid amount
            if strength >= 750:
                bid_n = 10
            elif strength >= 650:
                bid_n = 9
            elif strength >= 550:
                bid_n = 8
            elif strength >= 450:
                bid_n = 7
            elif strength >= 350:
                bid_n = 6
            elif strength >= 300:
                bid_n = 5
            elif strength >= 250:
                bid_n = 4
            elif strength >= 200:
                bid_n = 3
            elif strength >= 150:
                bid_n = 2
            elif strength >= 100:
                bid_n = 1
            else:
                continue  # Too weak, skip this contract

            # Check strict-increasing rule
            if bid_n > obs.current_high_bid:
                candidates.append((strength, bid_n, suit))

        # Evaluate HIGH contract (always, regardless of high/low card count)
        strength_high = score_hand_scalar(obs.hand, "high", None)
        if strength_high >= 500:
            bid_n = 8
        elif strength_high >= 450:
            bid_n = 7
        elif strength_high >= 400:
            bid_n = 6
        elif strength_high >= 350:
            bid_n = 5
        elif strength_high >= 280:
            bid_n = 4
        elif strength_high >= 200:
            bid_n = 3
        elif strength_high >= 150:
            bid_n = 2
        elif strength_high >= 100:
            bid_n = 1
        else:
            bid_n = 0

        if bid_n > obs.current_high_bid:
            candidates.append((strength_high, bid_n, "HIGH"))

        # Evaluate LOW contract (always, regardless of high/low card count)
        strength_low = score_hand_scalar(obs.hand, "low", None)
        if strength_low >= 500:
            bid_n = 8
        elif strength_low >= 450:
            bid_n = 7
        elif strength_low >= 400:
            bid_n = 6
        elif strength_low >= 350:
            bid_n = 5
        elif strength_low >= 280:
            bid_n = 4
        elif strength_low >= 200:
            bid_n = 3
        elif strength_low >= 150:
            bid_n = 2
        elif strength_low >= 100:
            bid_n = 1
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
    Feature-weighted bidder with configurable weights.

    Default formulas (R0, locked):
      suit: 1.0 * bowers + 0.5 * trump_count + 0.5 * offsuit_aces
      HIGH: 1.0 * offsuit_aces
      LOW:  1.0 * offsuit_tens_count

    R1 adds optional partner_weights for auction context features.
    The score maps directly to bid amount (floored).
    Named after the blog post's "specific model" baseline.
    """

    VERSION = HEURISTIC_BIDDER_VERSION

    _DEFAULT_FEATURE_WEIGHTS = {
        "suit": {"bowers": 1.0, "trump_count": 0.5, "offsuit_aces": 0.5},
        "high": {"offsuit_aces": 1.0},
        "low": {"offsuit_tens_count": 1.0},
    }

    def __init__(
        self,
        name: str = "modelo_especifico",
        feature_weights: dict | None = None,
        partner_weights: dict | None = None,
    ):
        super().__init__(name)
        self.feature_weights = feature_weights or self._DEFAULT_FEATURE_WEIGHTS
        self.partner_weights = partner_weights

    def _compute_partner_score(self, obs, contract_family):
        """Compute partner feature contribution to score."""
        if not self.partner_weights or not obs.auction_transcript:
            return 0.0
        from ..features.auction_context import extract_partner_features

        partner_feats = extract_partner_features(
            obs.seat, obs.auction_transcript, observer_best_contract=contract_family
        )
        return sum(w * partner_feats[f] for f, w in self.partner_weights.items())

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        from ..features.hand_eval import get_hand_features

        candidates = []

        # Evaluate suit contracts
        partner_score_suit = self._compute_partner_score(obs, "suit")
        for suit in ["C", "D", "H", "S"]:
            features = get_hand_features(obs.hand, "suit", suit)
            weights = self.feature_weights.get("suit", {})
            score = sum(w * features[f] for f, w in weights.items())
            score += partner_score_suit
            bid_n = int(score)  # floor
            if 1 <= bid_n <= 10 and bid_n > obs.current_high_bid:
                candidates.append((score, bid_n, suit))

        # Evaluate HIGH contract
        features_high = get_hand_features(obs.hand, "high", None)
        weights_high = self.feature_weights.get("high", {})
        score_high = sum(w * features_high[f] for f, w in weights_high.items())
        score_high += self._compute_partner_score(obs, "high")
        bid_n_high = int(score_high)
        if 1 <= bid_n_high <= 10 and bid_n_high > obs.current_high_bid:
            candidates.append((score_high, bid_n_high, "HIGH"))

        # Evaluate LOW contract
        features_low = get_hand_features(obs.hand, "low", None)
        weights_low = self.feature_weights.get("low", {})
        score_low = sum(w * features_low[f] for f, w in weights_low.items())
        score_low += self._compute_partner_score(obs, "low")
        bid_n_low = int(score_low)
        if 1 <= bid_n_low <= 10 and bid_n_low > obs.current_high_bid:
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

    VERSION = ARTIFACT_BIDDER_VERSION

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

        # Build sorted threshold lists from artifact params
        suit_thresh = sorted(
            (
                (int(k.split("_")[1]), v)
                for k, v in self.rules["suit_thresholds"].items()
            ),
            reverse=True,
        )
        hl_thresh = sorted(
            (
                (int(k.split("_")[1]), v)
                for k, v in self.rules["high_low_thresholds"].items()
            ),
            reverse=True,
        )

        # Evaluate suit contracts
        for suit in ["C", "D", "H", "S"]:
            strength = score_hand_scalar(obs.hand, "suit", suit)
            bid_n = 0
            for level, threshold in suit_thresh:
                if strength >= threshold:
                    bid_n = level
                    break
            if bid_n == 0:
                continue  # Too weak

            if bid_n > obs.current_high_bid:
                candidates.append((strength, bid_n, suit))

        # Evaluate HIGH contract (always, regardless of high/low card count)
        strength_high = score_hand_scalar(obs.hand, "high", None)
        bid_n = 0
        for level, threshold in hl_thresh:
            if strength_high >= threshold:
                bid_n = level
                break

        if bid_n > obs.current_high_bid:
            candidates.append((strength_high, bid_n, "HIGH"))

        # Evaluate LOW contract (always, regardless of high/low card count)
        strength_low = score_hand_scalar(obs.hand, "low", None)
        bid_n = 0
        for level, threshold in hl_thresh:
            if strength_low >= threshold:
                bid_n = level
                break

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

    Artifact format: accepts both olsa_v1 and hybrid_olsa_v1 artifacts.
    For hybrid_olsa_v1, uses the offensive sub-model (bidder's perspective)
    and ignores residual_variance / risk_lambda fields.
    """

    VERSION = ARTIFACT_BIDDER_VERSION

    def __init__(self, artifact_path: str, name: str = "olsa"):
        super().__init__(name)

        with open(artifact_path) as f:
            artifact = json.load(f)

        artifact_type = artifact.get("artifact_type")
        if artifact_type == "olsa_v1":
            raw_models = artifact["models"]
        elif artifact_type == "hybrid_olsa_v1":
            raw_models = {}
            for cf, model_data in artifact["payoff_model"].items():
                if "offensive" in model_data:
                    raw_models[cf] = model_data["offensive"]
                else:
                    raw_models[cf] = model_data
        else:
            raise ValueError(
                f"Expected artifact_type 'olsa_v1' or 'hybrid_olsa_v1', "
                f"got '{artifact_type}'"
            )

        self.models = {}
        for contract_family, model_data in raw_models.items():
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
                if 1 <= bid_n <= 10 and bid_n > obs.current_high_bid:
                    candidates.append((predicted_tricks, bid_n, suit))

        # Evaluate HIGH
        if "high" in self.models:
            features = get_hand_features(obs.hand, "high", None)
            predicted_tricks = self._predict("high", features)
            bid_n = math.floor(predicted_tricks)
            if 1 <= bid_n <= 10 and bid_n > obs.current_high_bid:
                candidates.append((predicted_tricks, bid_n, "HIGH"))

        # Evaluate LOW
        if "low" in self.models:
            features = get_hand_features(obs.hand, "low", None)
            predicted_tricks = self._predict("low", features)
            bid_n = math.floor(predicted_tricks)
            if 1 <= bid_n <= 10 and bid_n > obs.current_high_bid:
                candidates.append((predicted_tricks, bid_n, "LOW"))

        if not candidates:
            return BidAction.pass_bid()

        # Pick best: highest predicted tricks, break ties by bid amount, then alphabetically
        best = max(candidates, key=lambda x: (x[0], x[1], x[2]))
        return BidAction.bid(best[1], best[2])


def compute_best_bid(
    mu: float,
    sigma: float,
    current_high_bid: int,
    pass_threshold: float = 0.0,
    bid_level_search: bool = True,
    risk_lambda: float = 0.0,
    seed: int = 42,
    bid_bonus: float = 0.0,
) -> tuple[int, float] | None:
    """Find the best bid level for a single contract.

    Evaluates legal bid levels and returns the one with highest utility,
    or None if no level meets the pass threshold. This is the single source
    of truth for hybrid bid-selection logic — used by HybridOLSaBidder and
    by notebooks for analysis replay.

    Args:
        mu: Predicted trick mean from OLSa model.
        sigma: Predicted trick std dev (residual from training).
        current_high_bid: Current auction high bid (0 if opening).
        pass_threshold: Non-negative threshold t; pass if utility <= -t.
        bid_level_search: If True, search all legal levels. If False,
            evaluate floor(mu) only (v1 behavior).
        risk_lambda: CVaR risk penalty weight (0.0 = no penalty).
        seed: RNG seed for CVaR Monte Carlo draws.
        bid_bonus: Bid-proportional bonus added to make payoff (0.0 = no bonus,
            preserving v1 behavior). Positive values reward higher bids,
            counteracting the structural degeneracy where EV is always
            monotonically decreasing in bid level.

    Returns:
        (bid_n, utility) for the best legal level with utility > -pass_threshold,
        or None if no level meets the threshold.
    """
    min_bid = max(1, current_high_bid + 1)
    if min_bid > 10:
        return None

    if bid_level_search:
        search_range = range(min_bid, 11)
    else:
        # v1 behavior: evaluate floor(mu) only
        candidate = math.floor(mu)
        if candidate < min_bid or candidate > 10:
            return None
        search_range = range(candidate, candidate + 1)

    best_n = None
    best_utility = None

    for n in search_range:
        ev = _compute_ev_static(mu, sigma, n, bid_bonus)
        penalty = _compute_risk_penalty_static(mu, sigma, n, risk_lambda, seed)
        utility = ev - penalty

        if (
            best_utility is None
            or utility > best_utility
            or (utility == best_utility and n > best_n)
        ):
            best_utility = utility
            best_n = n

    if best_utility is None or best_utility <= -pass_threshold:
        return None

    return (best_n, best_utility)


# ---------------------------------------------------------------------------
# Static helpers for compute_best_bid (no class dependency)
# ---------------------------------------------------------------------------

_Z_CAP = 6.0
_CVAR_SEED_DEFAULT = 42
_CVAR_DRAWS = 1000
_CVAR_TAIL = 0.05


# ── Derivation: truncated normal EV ──
# Source: standard truncated normal distribution theory
# Formula:
#   Payoff: make (t >= bid) → net = 2t - 10; set (t < bid) → net = t - b - 10
#   Continuity correction: threshold = bid_n - 0.5 (half-integer boundary)
#   Conditional expectations: E[X|X≥k] = μ + σ·φ(z)/Φ̄(z)  (inverse Mills ratio)
#   Z_CAP = 6.0 prevents numerical overflow in extreme CDF/PDF tails
# Assumptions: tricks ~ N(μ, σ²), residual variance from OLS training
# See also: compute_ev_vectorized in nb56, analysis/sweep.py


def _compute_ev_static(
    mu: float, sigma: float, bid_n: int, bid_bonus: float = 0.0
) -> float:
    """Compute expected net-differential value using Gaussian model.

    Identical to HybridOLSaBidder._compute_ev but as a module-level function.
    """
    if sigma == 0.0:
        if mu >= bid_n:
            return 2.0 * mu - 10.0 + bid_bonus * bid_n
        else:
            return mu - bid_n - 10.0

    threshold = bid_n - 0.5
    z = (threshold - mu) / sigma
    z = max(-_Z_CAP, min(_Z_CAP, z))

    p_make = 1.0 - norm.cdf(z)
    p_set = 1.0 - p_make
    pdf_z = norm.pdf(z)

    if p_make > 1e-12:
        e_tricks_make = mu + sigma * pdf_z / p_make
    else:
        e_tricks_make = mu

    if p_set > 1e-12:
        e_tricks_set = mu - sigma * pdf_z / p_set
    else:
        e_tricks_set = mu

    make_ev = 2.0 * e_tricks_make - 10.0 + bid_bonus * bid_n
    set_ev = e_tricks_set - bid_n - 10.0

    return p_make * make_ev + p_set * set_ev


# ── Derivation: CVaR risk penalty (Monte Carlo) ──
# Source: Conditional Value-at-Risk (CVaR) via simulation
# Formula:
#   1. Draw 1000 samples from N(μ, σ²), compute net payoff for each
#   2. Sort nets ascending, take bottom 5% (tail_size = max(1, 50))
#   3. CVaR = mean of that tail
#   4. Penalty = max(0, -CVaR) × λ  (only penalizes downside risk)
# Assumptions: 1000 draws gives adequate precision for bid selection;
#   Monte Carlo avoids complex analytical truncated-normal CVaR formulas
# See also: plans/r0_v2_lambda_tuning_protocol.md


def _compute_risk_penalty_static(
    mu: float, sigma: float, bid_n: int, risk_lambda: float, seed: int
) -> float:
    """Compute CVaR risk penalty. Module-level version of _compute_risk_penalty."""
    if risk_lambda == 0.0:
        return 0.0

    if sigma == 0.0:
        if mu >= bid_n:
            net = 2.0 * mu - 10.0
        else:
            net = mu - bid_n - 10.0
        return max(0.0, -net) * risk_lambda

    rng = np.random.RandomState(seed)
    draws = rng.normal(mu, sigma, _CVAR_DRAWS)

    threshold = bid_n - 0.5
    nets = np.where(
        draws >= threshold,
        2.0 * draws - 10.0,
        draws - bid_n - 10.0,
    )

    tail_size = max(1, int(_CVAR_DRAWS * _CVAR_TAIL))
    sorted_nets = np.sort(nets)
    cvar = float(sorted_nets[:tail_size].mean())

    return max(0.0, -cvar) * risk_lambda


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

    VERSION = ARTIFACT_BIDDER_VERSION

    # z-cap to prevent numerical overflow in CDF/PDF
    _Z_CAP = 6.0
    # Fixed seed and draw count for CVaR Monte Carlo
    _CVAR_SEED = 42
    _CVAR_DRAWS = 1000
    _CVAR_TAIL = 0.05

    def __init__(
        self,
        artifact_path: str,
        risk_lambda: float = None,
        bid_level_search: bool = False,
        pass_threshold: float = 0.0,
        name: str = "hybrid_olsa",
        zero_partner_features: bool = False,
        bid_bonus: float = 0.0,
    ):
        super().__init__(name)
        self.bid_level_search = bool(bid_level_search)
        self.pass_threshold = float(pass_threshold)
        self.zero_partner_features = bool(zero_partner_features)
        self.bid_bonus = float(bid_bonus)

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

        # Compute net differential for each draw (continuity-corrected to match EV)
        threshold = bid_n - 0.5
        nets = np.where(
            draws >= threshold,
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

                # Merge partner features if model uses context features.
                # Always extract (even with empty transcript) so defaults (0)
                # are available — the first bidder has no transcript yet.
                if self.context_features:
                    from ..features.auction_context import extract_partner_features

                    partner_feats = extract_partner_features(
                        obs.seat,
                        obs.auction_transcript,
                        observer_best_contract=contract_family,
                    )
                    features = {**features, **partner_feats}

                    # Backward compat: old artifacts may expect
                    # partner_bid_confidence (removed PR #538).
                    # Derive from partner_bid_level / 10.
                    if (
                        "partner_bid_confidence" not in features
                        and "partner_bid_confidence" in self.context_features
                    ):
                        features["partner_bid_confidence"] = (
                            features.get("partner_bid_level", 0) / 10.0
                        )

                # Investigation C ablation: zero out partner features at
                # inference to test whether partner signal causes regression.
                if self.zero_partner_features:
                    for key in features:
                        if key.startswith("partner_"):
                            features[key] = 0.0

                mu = self._predict(contract_family, features, declaring=True)

                result = compute_best_bid(
                    mu=mu,
                    sigma=sigma,
                    current_high_bid=obs.current_high_bid,
                    pass_threshold=self.pass_threshold,
                    bid_level_search=self.bid_level_search,
                    risk_lambda=self.risk_lambda,
                    seed=self._CVAR_SEED,
                    bid_bonus=self.bid_bonus,
                )

                if result is None:
                    continue

                bid_n, utility = result

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

        if best_utility is None:
            return BidAction.pass_bid()

        return BidAction.bid(best_bid_n, best_contract)


# ===========================
#  Action-Value Bidding (R1.5)
# ===========================

# Canonical ordered list of the 39 hand feature names (matches get_hand_features() dict order).
_HAND_FEATURE_NAMES: List[str] = [
    "bowers",
    "trump_count",
    "offsuit_aces",
    "offsuit_non_ace_count",
    "hand_value",
    "trump_rb_count",
    "trump_lb_count",
    "trump_ace_count",
    "trump_king_count",
    "trump_queen_count",
    "trump_ten_count",
    "highest_trump_rank",
    "second_highest_trump_rank",
    "third_highest_trump_rank",
    "trump_power_sum",
    "trump_duplicate_pairs",
    "offsuit_king_count_total",
    "offsuit_queen_count_total",
    "offsuit_suits_with_ace",
    "offsuit_suits_with_double_ace",
    "offsuit_suits_with_ace_and_king",
    "void_count",
    "max_suit_len",
    "second_suit_len",
    "third_suit_len",
    "fourth_suit_len",
    "num_singletons",
    "num_doubletons",
    "offsuit_tens_count",
    "offsuit_length_3plus_count",
    "offsuit_best_rank_sum",
    "offsuit_secondbest_rank_sum",
    "double_ten_jack_count",
    "high_card_count",
    "low_card_count",
    "trump_count_x_void_count",
    "trump_count_x_offsuit_ace",
    "losing_tricks_count",
    "quick_tricks",
]

# Positional feature names (fixed across all schema versions)
_POSITIONAL_FEATURE_NAMES: List[str] = [
    "current_high_bid",
    "is_high",
    "is_low",
    "trump_C",
    "trump_D",
    "trump_H",
    "trump_S",
    "seat_rel_1",
    "seat_rel_2",
    "seat_rel_3",
]

# Position features: auction position and dealer flag (R1, LA-1)
# These sit between partner features and positional/legality features.
_POSITION_FEATURE_NAMES: List[str] = [
    "auction_position",
    "is_dealer",
]

# Known position feature names for _infer_partner_features exclusion
_POSITION_FEATURE_SET: frozenset = frozenset(_POSITION_FEATURE_NAMES)

# Opponent feature names (R2): 12 features (6 left + 6 right)
_OPPONENT_FEATURE_NAMES: List[str] = [
    "opp_left_level_same_suit",
    "opp_left_level_same_color",
    "opp_left_level_off_color",
    "opp_left_level_high",
    "opp_left_level_low",
    "opp_left_passed",
    "opp_right_level_same_suit",
    "opp_right_level_same_color",
    "opp_right_level_off_color",
    "opp_right_level_high",
    "opp_right_level_low",
    "opp_right_passed",
]

# Known opponent feature names for _infer_partner_features exclusion
_OPPONENT_FEATURE_SET: frozenset = frozenset(_OPPONENT_FEATURE_NAMES)

# State feature names: 39 hand + 6 partner_v2 + 2 position + 12 opponent + 10 positional = 69
# This is the R2 canonical default. Artifact-driven extraction may use different
# partner features (v7: 3 features, v2: 6 features) and may omit opponent features
# (R0/R1 artifacts), but hand, position, and positional features are fixed.
STATE_FEATURE_NAMES: List[str] = (
    _HAND_FEATURE_NAMES
    + [
        "partner_level_same_suit",
        "partner_level_same_color",
        "partner_level_off_color",
        "partner_level_high",
        "partner_level_low",
        "partner_passed",
    ]
    + _POSITION_FEATURE_NAMES
    + _OPPONENT_FEATURE_NAMES
    + _POSITIONAL_FEATURE_NAMES
)


def _infer_partner_features(feature_names: List[str]) -> List[str]:
    """Extract the partner feature subset from a full feature list.

    Partner features sit between hand features (39) and positional features (10).
    The hand and positional blocks are fixed across schema versions; only the
    partner block varies (v7: 3 features, v2: 6 features).

    Position features (auction_position, is_dealer) and opponent features
    (opp_left_*, opp_right_*) may sit between partner and positional blocks —
    they are excluded from the returned partner list.

    If no positional features are present (R0 hand-only models), there are no
    partner features either — returns an empty list.

    Args:
        feature_names: Full ordered feature list from an artifact model.

    Returns:
        The partner feature names (the slice between hand and positional blocks,
        excluding position and opponent features). Empty list for R0 hand-only models.
    """
    hand_end = len(_HAND_FEATURE_NAMES)  # 39
    if "current_high_bid" not in feature_names:
        # No positional features = no partner features (R0 hand-only model)
        return []
    positional_start = feature_names.index("current_high_bid")
    # Position and opponent features sit between partner and positional blocks — exclude them
    _excluded = _POSITION_FEATURE_SET | _OPPONENT_FEATURE_SET
    partner_names = [
        n for n in feature_names[hand_end:positional_start] if n not in _excluded
    ]
    # partner_names can be empty (model with positional but no partner features)
    return partner_names


# Action feature names appended to state for per-contract models.
# R0-R2 artifacts use the 2-element base set; R3+ artifacts include moon/loner.
ACTION_FEATURE_NAMES_BASE: List[str] = ["bid_n", "bid_n_sq"]
ACTION_FEATURE_NAMES: List[str] = ["bid_n", "bid_n_sq", "is_moon", "is_loner"]

# Interaction feature names computed from state features at inference time.
# Each maps to (state_index_a, state_index_b) — product of those state elements.
# These are only present in "interaction" feature-set artifacts.
INTERACTION_FEATURE_NAMES: List[str] = [
    "bowers_x_trump_count",
    "trump_count_sq",
    "bowers_sq",
]

_INTERACTION_INDICES: List[Tuple[int, int]] = [
    (0, 1),  # bowers(0) * trump_count(1)
    (1, 1),  # trump_count(1) * trump_count(1)
    (0, 0),  # bowers(0) * bowers(0)
]


def extract_state_features(
    obs: BiddingObservation,
    contract_family: str,
    trump_suit: Optional[str],
    partner_feature_names: Optional[List[str]] = None,
    include_positional: bool = True,
) -> np.ndarray:
    """Extract the state feature vector for a candidate action.

    Args:
        obs: Current bidding observation.
        contract_family: One of "suit", "high", "low", or "none".
            "none" is used for pass actions (no contract context).
        trump_suit: Trump suit letter for suit contracts, None otherwise.
        partner_feature_names: Ordered list of partner feature names to extract.
            If None, uses v2 defaults (6 suit-relative features). Artifact-driven
            bidders pass their artifact's partner feature names here to support
            schema evolution (v7 artifacts pass 3-feature list).
        include_positional: Whether to include the position (2) and
            positional/legality (10) features. False for R0 hand-only models
            that have no positional features. Defaults to True.

    Returns:
        np.ndarray with features in order:
        - With positional: hand (39) + partner (N) + position (2) + opponent (12)
          + positional (10). Default shape is (69,) for R2 schema (v2 partner,
          6 features + 12 opponent features).
        - Without positional: hand (39) only (R0 hand-only models).

    Note on pass ("none") encoding:
        get_hand_features() requires a contract_type; there is no contract-neutral
        path without modifying the frozen hand_eval.py. We use "high" as proxy
        because it has no trump dependency (no bowers, no trump suit reranking),
        making it the least contract-specific option. The indicator dummies
        (is_high, is_low, trump_*) are all zeroed for "none", so only the 39 hand
        features carry the "high" interpretation. This is symmetric: the dataset
        generator uses the same extract_state_features("none", None) call, so the
        pass model trains and infers on identically-encoded features.
    """
    from ..features.hand_eval import get_hand_features

    # Hand features (39): "high" proxy for "none" — see docstring note above.
    hand_contract = contract_family if contract_family != "none" else "high"
    hand_feats = get_hand_features(obs.hand, hand_contract, trump_suit)
    hand_arr = np.array(
        [float(hand_feats[k]) for k in _HAND_FEATURE_NAMES], dtype=np.float64
    )

    if not include_positional:
        # R0 hand-only: no partner or positional features
        return hand_arr

    from ..features.auction_context import (
        OPPONENT_FEATURE_NAMES,
        PARTNER_FEATURE_NAMES_V2,
        extract_opponent_features,
        extract_partner_features,
        extract_partner_features_v2,
    )

    if partner_feature_names is None:
        partner_feature_names = PARTNER_FEATURE_NAMES_V2

    # Detect which partner extractor to use based on feature names.
    # v2 features start with "partner_level_"; v7 features start with "partner_bid_".
    _v2_names = set(PARTNER_FEATURE_NAMES_V2)
    if set(partner_feature_names) <= _v2_names:
        # v2 partner features (R1 default)
        partner_family = contract_family if contract_family != "none" else None
        partner_feats = extract_partner_features_v2(
            obs.seat,
            obs.auction_transcript,
            observer_contract_type=partner_family,
            observer_trump_suit=trump_suit,
        )
    else:
        # v7 partner features (backward compat for loaded artifacts)
        partner_family = contract_family if contract_family != "none" else None
        partner_feats = extract_partner_features(
            obs.seat, obs.auction_transcript, partner_family
        )
    partner_arr = np.array(
        [float(partner_feats[k]) for k in partner_feature_names],
        dtype=np.float64,
    )

    # Position features (2): auction_position + is_dealer
    auction_position = float((obs.seat - obs.dealer_seat - 1) % 4)
    is_dealer = float(int(obs.seat == obs.dealer_seat))
    position_arr = np.array(
        [auction_position, is_dealer],
        dtype=np.float64,
    )

    # Opponent features (12): 6 left + 6 right (R2)
    opp_family = contract_family if contract_family != "none" else None
    opp_feats = extract_opponent_features(
        obs.seat,
        obs.auction_transcript,
        observer_contract_type=opp_family,
        observer_trump_suit=trump_suit,
    )
    opp_arr = np.array(
        [float(opp_feats[k]) for k in OPPONENT_FEATURE_NAMES],
        dtype=np.float64,
    )

    # Positional / legality features (10)
    current_high_bid = float(obs.current_high_bid)

    # Contract indicators: "none" state → both 0
    is_high = 1.0 if contract_family == "high" else 0.0
    is_low = 1.0 if contract_family == "low" else 0.0

    # Trump dummies: suit contracts get one-hot; high/low/none → all zeros
    trump_c = 1.0 if trump_suit == "C" else 0.0
    trump_d = 1.0 if trump_suit == "D" else 0.0
    trump_h = 1.0 if trump_suit == "H" else 0.0
    trump_s = 1.0 if trump_suit == "S" else 0.0

    # Seat relative to dealer (one-hot, dealer=reference → 3 dummies)
    relative_seat = (obs.seat - obs.dealer_seat) % 4
    seat_rel_1 = 1.0 if relative_seat == 1 else 0.0
    seat_rel_2 = 1.0 if relative_seat == 2 else 0.0
    seat_rel_3 = 1.0 if relative_seat == 3 else 0.0

    positional_arr = np.array(
        [
            current_high_bid,
            is_high,
            is_low,
            trump_c,
            trump_d,
            trump_h,
            trump_s,
            seat_rel_1,
            seat_rel_2,
            seat_rel_3,
        ],
        dtype=np.float64,
    )

    return np.concatenate(
        [hand_arr, partner_arr, position_arr, opp_arr, positional_arr]
    )


def extract_action_features(
    bid_n: int,
    bid_type: str = "regular",
    *,
    include_moon_loner: bool = True,
) -> np.ndarray:
    """Extract action feature vector for a bid.

    Args:
        bid_n: The bid level (0-10).
        bid_type: One of "regular", "moon", or "loner". Default "regular"
            for backward compatibility with R0-R2 models.
        include_moon_loner: If True, return 4 features [bid_n, bid_n_sq,
            is_moon, is_loner]. If False, return only 2 features
            [bid_n, bid_n_sq] (R0-R2 backward compat).

    Returns:
        np.ndarray of shape (4,) or (2,) depending on include_moon_loner.
    """
    base = [float(bid_n), float(bid_n * bid_n)]
    if include_moon_loner:
        is_moon = 1.0 if bid_type == "moon" else 0.0
        is_loner = 1.0 if bid_type == "loner" else 0.0
        base.extend([is_moon, is_loner])
    return np.array(base, dtype=np.float64)


def compute_interaction_features(state: np.ndarray) -> np.ndarray:
    """Compute interaction features from a state vector.

    Returns a small array of interaction terms (products of state elements)
    matching INTERACTION_FEATURE_NAMES order.
    """
    return np.array(
        [state[a] * state[b] for a, b in _INTERACTION_INDICES],
        dtype=np.float64,
    )


def predict_ols(model_dict: dict, features: np.ndarray) -> float:
    """Dot-product prediction from an action_value_olsa_v1 model dict.

    Each model_dict has "coefficients" (array) and optional "intercept" (float).
    """
    coefficients = np.asarray(model_dict["coefficients"], dtype=np.float64)
    intercept = float(model_dict.get("intercept", 0.0))
    return float(np.dot(coefficients, features) + intercept)


# ── Load-time behavioral sanity checks ───────────────────

# These are lightweight checks (~1ms) that catch catastrophically broken
# artifacts at load time. They use a single synthetic observation and verify
# that bid-10 is NOT the argmax for every contract family. A pathological
# artifact (R²=0.18, "always bids 10") fails this immediately.
#
# Full behavioral validation (multi-hand, statistics) is in
# scripts/internal/validate_action_value_artifact.py.

_SANITY_CHECK_HAND = [
    Card(rank="T", suit="C"),
    Card(rank="T", suit="D"),
    Card(rank="T", suit="H"),
    Card(rank="T", suit="S"),
    Card(rank="J", suit="C"),
    Card(rank="Q", suit="D"),
    Card(rank="Q", suit="H"),
    Card(rank="Q", suit="S"),
    Card(rank="K", suit="C"),
    Card(rank="J", suit="S"),
]

_SANITY_CHECK_OBS = BiddingObservation(
    hand=_SANITY_CHECK_HAND,
    seat=1,
    dealer_seat=0,
    current_high_bid=0,
    allowed_contracts=("C", "D", "H", "S", "HIGH", "LOW"),
    auction_transcript=(),
)


def _validate_artifact_features(
    model_feature_names: List[str],
    has_interactions: bool,
) -> Tuple[List[str], bool]:
    """Validate and infer partner features from an artifact model's feature_names.

    Shared validation logic for all action-value bidder classes. Checks that
    the artifact's feature_names have the expected structure:
        hand (39) + partner (N) + position (0-2) + opponent (0-12)
        + positional (10) [+ interaction (3)] + action (2 or 4)
    or for R0/constrained/selected hand-only models:
        hand_subset (M) + action (2 or 4)  where M <= 39

    Returns a tuple of (inferred partner feature names, has_positional).

    Raises:
        ValueError: If feature_names don't match the expected structure.
    """
    # Detect action feature size: R3+ artifacts have 4 (bid_n, bid_n_sq,
    # is_moon, is_loner); R0-R2 artifacts have 2 (bid_n, bid_n_sq).
    n_action_full = len(ACTION_FEATURE_NAMES)
    n_action_base = len(ACTION_FEATURE_NAMES_BASE)
    tail_full = list(model_feature_names[-n_action_full:])
    tail_base = list(model_feature_names[-n_action_base:])
    if tail_full == ACTION_FEATURE_NAMES:
        n_action = n_action_full
        action_names_used = ACTION_FEATURE_NAMES
    elif tail_base == ACTION_FEATURE_NAMES_BASE:
        n_action = n_action_base
        action_names_used = ACTION_FEATURE_NAMES_BASE
    else:
        raise ValueError(
            f"Artifact feature_names do not end with recognized action features. "
            f"Expected {ACTION_FEATURE_NAMES} or {ACTION_FEATURE_NAMES_BASE}, "
            f"got {tail_full}."
        )

    # Strip action features from the end to get state features
    if has_interactions:
        n_interaction = len(INTERACTION_FEATURE_NAMES)
        state_plus_interaction = model_feature_names[:-(n_action)]
        state_names = state_plus_interaction[:-(n_interaction)]
    else:
        state_names = model_feature_names[:-(n_action)]

    partner_names = _infer_partner_features(state_names)
    has_positional = "current_high_bid" in state_names

    # Detect position and opponent features between partner and positional blocks
    hand_end = len(_HAND_FEATURE_NAMES)
    positional_start = (
        state_names.index("current_high_bid") if has_positional else len(state_names)
    )
    middle_names = state_names[hand_end:positional_start]
    position_names = [n for n in middle_names if n in _POSITION_FEATURE_SET]
    opponent_names = [n for n in middle_names if n in _OPPONENT_FEATURE_SET]

    # Rebuild expected full feature list and validate
    if has_positional:
        # Standard layout: exact match required
        expected_state = (
            list(_HAND_FEATURE_NAMES)
            + list(partner_names)
            + list(position_names)
            + list(opponent_names)
            + list(_POSITIONAL_FEATURE_NAMES)
        )
        if has_interactions:
            expected_full = (
                expected_state + INTERACTION_FEATURE_NAMES + action_names_used
            )
        else:
            expected_full = expected_state + action_names_used

        if list(model_feature_names) != expected_full:
            raise ValueError(
                f"Artifact feature_names structural mismatch. "
                f"Expected {len(expected_full)} features "
                f"(39 hand + {len(partner_names)} partner"
                f"{f' + {len(position_names)} position' if position_names else ''}"
                f"{f' + {len(opponent_names)} opponent' if opponent_names else ''}"
                f" + 10 positional"
                f"{' + 3 interaction' if has_interactions else ''}"
                f" + {n_action} action), "
                f"got {len(model_feature_names)} features."
            )
    else:
        # R0/constrained/selected: state features should be a subset of
        # known hand features, partner v2 features, position features,
        # opponent features, and positional/legality features. Forward
        # selection from the full state feature set may keep any subset
        # of these (e.g. seat_rel_2 without current_high_bid), so we
        # accept all categories as valid.
        from ..features.auction_context import PARTNER_FEATURE_NAMES_V2

        valid_set = (
            set(_HAND_FEATURE_NAMES)
            | set(PARTNER_FEATURE_NAMES_V2)
            | _POSITION_FEATURE_SET
            | _OPPONENT_FEATURE_SET
            | set(_POSITIONAL_FEATURE_NAMES)
        )
        unknown = [f for f in state_names if f not in valid_set]
        if unknown:
            raise ValueError(
                f"Artifact feature_names structural mismatch. "
                f"Non-positional model contains unknown state features "
                f"(not in hand/partner/position/opponent/positional feature set): {unknown}"
            )

        # Verify action features are at the expected positions
        actual_action = model_feature_names[-(n_action):]
        if list(actual_action) != list(action_names_used):
            raise ValueError(
                f"Artifact feature_names structural mismatch. "
                f"Expected action features {action_names_used} at end, "
                f"got {actual_action}."
            )

    return list(partner_names), has_positional


def _detect_action_feature_count(model_feature_names: List[str]) -> int:
    """Detect whether a model uses 2 (base) or 4 (extended) action features.

    Returns the number of action features at the tail of model_feature_names.
    """
    n_full = len(ACTION_FEATURE_NAMES)
    n_base = len(ACTION_FEATURE_NAMES_BASE)
    if (
        len(model_feature_names) >= n_full
        and list(model_feature_names[-n_full:]) == ACTION_FEATURE_NAMES
    ):
        return n_full
    if (
        len(model_feature_names) >= n_base
        and list(model_feature_names[-n_base:]) == ACTION_FEATURE_NAMES_BASE
    ):
        return n_base
    # Fallback — let validation catch mismatches
    return n_full


def _validate_pass_model_features(
    pass_feature_names: List[str],
    partner_feature_names: List[str],
    has_interactions: bool,
    has_positional: bool = True,
) -> None:
    """Validate pass model feature_names against inferred partner features.

    Pass models use state features only (no action features).
    """
    if has_positional:
        # Detect position and opponent features in pass model's feature list
        hand_end = len(_HAND_FEATURE_NAMES)
        positional_start = (
            pass_feature_names.index("current_high_bid")
            if "current_high_bid" in pass_feature_names
            else len(pass_feature_names)
        )
        middle_names = pass_feature_names[hand_end:positional_start]
        position_names = [n for n in middle_names if n in _POSITION_FEATURE_SET]
        opponent_names = [n for n in middle_names if n in _OPPONENT_FEATURE_SET]

        expected_state = (
            list(_HAND_FEATURE_NAMES)
            + list(partner_feature_names)
            + list(position_names)
            + list(opponent_names)
            + list(_POSITIONAL_FEATURE_NAMES)
        )
        if has_interactions:
            expected = expected_state + INTERACTION_FEATURE_NAMES
        else:
            expected = expected_state

        if list(pass_feature_names) != expected:
            raise ValueError(
                f"Artifact pass model feature_names mismatch. "
                f"Expected {len(expected)} state features, "
                f"got {len(pass_feature_names)} features."
            )
    else:
        # R0/constrained/selected: pass features should be subset of
        # known hand features, partner v2 features, position features,
        # opponent features, and positional/legality features. Forward
        # selection from the full feature set may keep any subset of
        # these (e.g. seat_rel_2 without current_high_bid).
        from ..features.auction_context import PARTNER_FEATURE_NAMES_V2

        valid_set = (
            set(_HAND_FEATURE_NAMES)
            | set(PARTNER_FEATURE_NAMES_V2)
            | _POSITION_FEATURE_SET
            | _OPPONENT_FEATURE_SET
            | set(_POSITIONAL_FEATURE_NAMES)
        )
        unknown = [f for f in pass_feature_names if f not in valid_set]
        if unknown:
            raise ValueError(
                f"Artifact pass model feature_names mismatch. "
                f"Non-positional pass model contains unknown features "
                f"(not in hand/partner/position/opponent/positional feature set): {unknown}"
            )


def _check_ols_predictions_sane(
    models: dict[str, dict],
    pass_model: dict,
    partner_feature_names: Optional[List[str]] = None,
    has_interactions: bool = False,
    include_positional: bool = True,
    hand_indices: Optional[dict[str, np.ndarray]] = None,
    has_moon_loner: bool = True,
) -> None:
    """Quick sanity check that OLS predictions aren't degenerate.

    Checks that bid-10 is NOT predicted as optimal for every suit on a
    weak synthetic hand. A valid model should not predict bid-10 as best
    for a hand with no bowers and weak trump.

    Raises ValueError if the check fails.
    """
    bid_10_best_count = 0

    for family in ("suit", "high", "low"):
        trump = "H" if family == "suit" else None
        state = extract_state_features(
            _SANITY_CHECK_OBS,
            family,
            trump,
            partner_feature_names=partner_feature_names,
            include_positional=include_positional,
        )
        if hand_indices and family in hand_indices:
            state = state[hand_indices[family]]
        # Compare bid-10 value vs bid-1 value
        parts_10 = [state]
        parts_1 = [state]
        if has_interactions:
            interactions = compute_interaction_features(state)
            parts_10.append(interactions)
            parts_1.append(interactions)
        parts_10.append(extract_action_features(10, include_moon_loner=has_moon_loner))
        parts_1.append(extract_action_features(1, include_moon_loner=has_moon_loner))
        feats_10 = np.concatenate(parts_10)
        feats_1 = np.concatenate(parts_1)
        val_10 = predict_ols(models[family], feats_10)
        val_1 = predict_ols(models[family], feats_1)
        if val_10 > val_1:
            bid_10_best_count += 1

    if bid_10_best_count == 3:
        raise ValueError(
            "Behavioral sanity check FAILED: bid-10 is predicted as better than "
            "bid-1 for ALL contract families on a weak hand. This indicates a "
            "pathological artifact (e.g., wrong target, stale model with low R²). "
            "Use skip_behavioral_check=True to bypass this check for testing."
        )


def _check_gbt_predictions_sane(
    gbt_models: dict[str, object],
    partner_feature_names: Optional[List[str]] = None,
    include_positional: bool = True,
    hand_indices: Optional[dict[str, np.ndarray]] = None,
    has_moon_loner: bool = True,
) -> None:
    """Quick sanity check that GBT predictions aren't degenerate.

    Same logic as _check_ols_predictions_sane but for GBT models.
    """
    bid_10_best_count = 0

    for family in ("suit", "high", "low"):
        trump = "H" if family == "suit" else None
        state = extract_state_features(
            _SANITY_CHECK_OBS,
            family,
            trump,
            partner_feature_names=partner_feature_names,
            include_positional=include_positional,
        )
        if hand_indices and family in hand_indices:
            state = state[hand_indices[family]]
        feats_10 = np.concatenate(
            [state, extract_action_features(10, include_moon_loner=has_moon_loner)]
        )
        feats_1 = np.concatenate(
            [state, extract_action_features(1, include_moon_loner=has_moon_loner)]
        )
        val_10 = float(gbt_models[family].predict(feats_10.reshape(1, -1))[0])
        val_1 = float(gbt_models[family].predict(feats_1.reshape(1, -1))[0])
        if val_10 > val_1:
            bid_10_best_count += 1

    if bid_10_best_count == 3:
        raise ValueError(
            "Behavioral sanity check FAILED: bid-10 is predicted as better than "
            "bid-1 for ALL contract families on a weak hand. This indicates a "
            "pathological artifact. "
            "Use skip_behavioral_check=True to bypass this check for testing."
        )


class ActionValueBidder(BiddingPolicy):
    """Action-value bidder: selects the legal action with highest
    predicted E[net_points].

    Uses per-contract OLS models (suit, high, low) plus a separate
    pass model. No hand-coded utility, no Gaussian EV, no sigma.

    Artifact schema: action_value_olsa_v1
    """

    VERSION = ARTIFACT_BIDDER_VERSION

    def __init__(
        self,
        artifact_path: str,
        name: str = "action_value",
        skip_behavioral_check: bool = False,
    ):
        super().__init__(name=name)

        with open(artifact_path) as f:
            artifact = json.load(f)

        schema = artifact.get("schema_version")
        if schema != "action_value_olsa_v1":
            raise ValueError(
                f"Expected schema_version 'action_value_olsa_v1', got '{schema}'"
            )

        # Reject quarantined artifacts
        status = artifact.get("status", "active")
        if status == "quarantined":
            raise ValueError(
                f"Artifact is quarantined (status='quarantined'): {artifact_path}"
            )

        models = artifact["models"]

        # R² quality warning — catches wrong-target or stale artifacts
        for family in ("suit", "high", "low"):
            r2 = models[family].get("r_squared")
            if r2 is not None and r2 < _R2_WARNING_THRESHOLD:
                logger.warning(
                    "Low R² for %s model: %.4f < %.2f — possible wrong-target "
                    "or stale artifact: %s",
                    family,
                    r2,
                    _R2_WARNING_THRESHOLD,
                    artifact_path,
                )
        self.models = {
            "suit": models["suit"],
            "high": models["high"],
            "low": models["low"],
        }
        self.pass_model = models["pass"]
        self.context_features = artifact.get("metadata", {}).get("context_features", [])

        # Detect interaction feature set from artifact metadata
        feature_set = artifact.get("feature_set", "full")
        self._has_interactions = feature_set == "interaction"

        # Artifact-driven feature validation: infer partner features from the
        # artifact's stored feature_names rather than the global STATE_FEATURE_NAMES.
        # This enables v7/v8 schema coexistence in H2H batteries.
        for family in ("suit", "high", "low"):
            model = self.models[family]
            if "feature_names" not in model:
                raise ValueError(
                    f"Artifact {family} model missing required 'feature_names'"
                )
        # Use suit model as reference for partner feature inference
        self._partner_feature_names, self._has_positional = _validate_artifact_features(
            list(self.models["suit"]["feature_names"]),
            self._has_interactions,
        )
        # Validate remaining models have consistent feature_names
        for family in ("high", "low"):
            partner_check, pos_check = _validate_artifact_features(
                list(self.models[family]["feature_names"]),
                self._has_interactions,
            )
            if partner_check != self._partner_feature_names:
                raise ValueError(
                    f"Artifact {family} model has different partner features than suit: "
                    f"{partner_check} vs {self._partner_feature_names}"
                )
        if "feature_names" not in self.pass_model:
            raise ValueError("Artifact pass model missing required 'feature_names'")
        _validate_pass_model_features(
            list(self.pass_model["feature_names"]),
            self._partner_feature_names,
            self._has_interactions,
            has_positional=self._has_positional,
        )

        # Detect whether artifact uses 4 (moon/loner) or 2 (base) action features.
        # Must be computed UNCONDITIONALLY — R3 models have positional=True AND
        # moon/loner features.
        self._has_moon_loner = _detect_action_feature_count(
            list(self.models["suit"]["feature_names"])
        ) == len(ACTION_FEATURE_NAMES)

        # For R0/selected models: precompute per-family hand feature indices
        # so choose_bid() can select the right subset from the full state vector.
        # R1/R2 forward-selected artifacts may include partner/position/opponent
        # features (e.g., partner_passed) that are not in _HAND_FEATURE_NAMES.
        # When this happens, map indices against STATE_FEATURE_NAMES (69 features)
        # and extract the full state vector at inference time.
        self._hand_indices: dict[str, Optional[np.ndarray]] = {}
        hand_name_set = set(_HAND_FEATURE_NAMES)
        if not self._has_positional:
            n_action = _detect_action_feature_count(
                list(self.models["suit"]["feature_names"])
            )
            # Collect all state feature names to detect non-hand features
            all_state_names: list[str] = []
            for family in ("suit", "high", "low"):
                all_state_names.extend(
                    self.models[family]["feature_names"][:-(n_action)]
                )
            all_state_names.extend(self.pass_model["feature_names"])
            self._needs_full_state = any(
                n not in hand_name_set for n in all_state_names
            )

            if self._needs_full_state:
                name_to_idx = {n: i for i, n in enumerate(STATE_FEATURE_NAMES)}
            else:
                name_to_idx = {n: i for i, n in enumerate(_HAND_FEATURE_NAMES)}

            for family in ("suit", "high", "low"):
                state_names = self.models[family]["feature_names"][:-(n_action)]
                self._hand_indices[family] = np.array(
                    [name_to_idx[n] for n in state_names]
                )
            pass_names = list(self.pass_model["feature_names"])
            self._hand_indices["pass"] = np.array([name_to_idx[n] for n in pass_names])
        else:
            self._needs_full_state = False

        if not skip_behavioral_check:
            # Match _select_state: pass None for partner_feature_names when
            # _needs_full_state so extract_state_features returns all 69 features
            sanity_partner = (
                None if self._needs_full_state else self._partner_feature_names
            )
            _check_ols_predictions_sane(
                self.models,
                self.pass_model,
                sanity_partner,
                has_interactions=self._has_interactions,
                include_positional=self._has_positional or self._needs_full_state,
                hand_indices=self._hand_indices if not self._has_positional else None,
                has_moon_loner=self._has_moon_loner,
            )

    def _select_state(
        self, obs: BiddingObservation, family: str, trump_suit: Optional[str]
    ) -> np.ndarray:
        """Extract state features, selecting the appropriate subset for the model."""
        contract_family = family if family != "pass" else "none"
        state = extract_state_features(
            obs,
            contract_family,
            trump_suit,
            partner_feature_names=(
                None if self._needs_full_state else self._partner_feature_names
            ),
            include_positional=self._has_positional or self._needs_full_state,
        )
        if not self._has_positional and family in self._hand_indices:
            state = state[self._hand_indices[family]]
        return state

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        """Select the legal action with highest predicted E[net_points]."""
        legal = enumerate_legal_actions(obs, include_moon_loner=self._has_moon_loner)

        best_value = float("-inf")
        best_action = BidAction.pass_bid()

        for action in legal:
            if action.is_pass():
                # Pass model: state-only features with "none" contract encoding
                state = self._select_state(obs, "pass", None)
                if self._has_interactions:
                    interactions = compute_interaction_features(state)
                    state = np.concatenate([state, interactions])
                value = predict_ols(self.pass_model, state)
            else:
                contract_type, trump_suit = action.to_contract_tuple()
                family = contract_type  # "suit", "high", or "low"
                state = self._select_state(obs, family, trump_suit)
                if self._has_interactions:
                    interactions = compute_interaction_features(state)
                    state = np.concatenate([state, interactions])
                action_feats = extract_action_features(
                    action.n,
                    action.bid_type,
                    include_moon_loner=self._has_moon_loner,
                )
                features = np.concatenate([state, action_feats])
                value = predict_ols(self.models[family], features)

            if value > best_value:
                best_value = value
                best_action = action

        return best_action


class GBTActionValueBidder(BiddingPolicy):
    """Action-value bidder using Gradient Boosted Tree regressors.

    Uses per-contract GBT models (suit, high, low) plus a separate
    pass model. Structurally identical to ActionValueBidder but uses
    sklearn GBT predict() instead of OLS dot-product.

    Artifact schema: action_value_gbt_v1
    """

    VERSION = ARTIFACT_BIDDER_VERSION

    def __init__(
        self,
        artifact_path: str,
        name: str = "gbt_action_value",
        skip_behavioral_check: bool = False,
    ):
        super().__init__(name=name)

        import joblib

        artifact_dir = Path(artifact_path).parent

        with open(artifact_path) as f:
            artifact = json.load(f)

        schema = artifact.get("schema_version")
        if schema != "action_value_gbt_v1":
            raise ValueError(
                f"Expected schema_version 'action_value_gbt_v1', got '{schema}'"
            )

        # Reject quarantined artifacts
        status = artifact.get("status", "active")
        if status == "quarantined":
            raise ValueError(
                f"Artifact is quarantined (status='quarantined'): {artifact_path}"
            )

        models_meta = artifact["models"]

        # R² quality warning — catches wrong-target or stale artifacts
        for family in ("suit", "high", "low"):
            r2 = models_meta[family].get("r_squared")
            if r2 is not None and r2 < _R2_WARNING_THRESHOLD:
                logger.warning(
                    "Low R² for %s model: %.4f < %.2f — possible wrong-target "
                    "or stale artifact: %s",
                    family,
                    r2,
                    _R2_WARNING_THRESHOLD,
                    artifact_path,
                )

        # Load sklearn GBT model objects from .joblib files
        self.gbt_models = {}
        for family in ("suit", "high", "low"):
            model_path = artifact_dir / models_meta[family]["model_file"]
            self.gbt_models[family] = joblib.load(model_path)

        self.pass_gbt = joblib.load(artifact_dir / models_meta["pass"]["model_file"])

        # Detect interaction feature set from artifact metadata
        feature_set = artifact.get("feature_set", "full")
        self._has_interactions = feature_set == "interaction"

        # Artifact-driven feature validation (same pattern as ActionValueBidder)
        for family in ("suit", "high", "low"):
            meta = models_meta[family]
            if "feature_names" not in meta:
                raise ValueError(
                    f"Artifact {family} model missing required 'feature_names'"
                )
        self._partner_feature_names, self._has_positional = _validate_artifact_features(
            list(models_meta["suit"]["feature_names"]),
            self._has_interactions,
        )
        for family in ("high", "low"):
            partner_check, pos_check = _validate_artifact_features(
                list(models_meta[family]["feature_names"]),
                self._has_interactions,
            )
            if partner_check != self._partner_feature_names:
                raise ValueError(
                    f"Artifact {family} model has different partner features than suit: "
                    f"{partner_check} vs {self._partner_feature_names}"
                )
        if "feature_names" not in models_meta["pass"]:
            raise ValueError("Artifact pass model missing required 'feature_names'")
        _validate_pass_model_features(
            list(models_meta["pass"]["feature_names"]),
            self._partner_feature_names,
            self._has_interactions,
            has_positional=self._has_positional,
        )

        # Detect whether artifact uses 4 (moon/loner) or 2 (base) action features.
        # Must be computed UNCONDITIONALLY — R3 models have positional=True AND
        # moon/loner features.
        self._has_moon_loner = _detect_action_feature_count(
            list(models_meta["suit"]["feature_names"])
        ) == len(ACTION_FEATURE_NAMES)

        # For R0/selected models: precompute per-family hand feature indices.
        # R1 forward-selected artifacts may include partner/position features
        # that are not in _HAND_FEATURE_NAMES — use STATE_FEATURE_NAMES when needed.
        self._hand_indices: dict[str, Optional[np.ndarray]] = {}
        hand_name_set = set(_HAND_FEATURE_NAMES)
        if not self._has_positional:
            n_action = _detect_action_feature_count(
                list(models_meta["suit"]["feature_names"])
            )
            all_state_names: list[str] = []
            for family in ("suit", "high", "low"):
                all_state_names.extend(
                    models_meta[family]["feature_names"][:-(n_action)]
                )
            all_state_names.extend(models_meta["pass"]["feature_names"])
            self._needs_full_state = any(
                n not in hand_name_set for n in all_state_names
            )

            if self._needs_full_state:
                name_to_idx = {n: i for i, n in enumerate(STATE_FEATURE_NAMES)}
            else:
                name_to_idx = {n: i for i, n in enumerate(_HAND_FEATURE_NAMES)}

            for family in ("suit", "high", "low"):
                state_names = models_meta[family]["feature_names"][:-(n_action)]
                self._hand_indices[family] = np.array(
                    [name_to_idx[n] for n in state_names]
                )
            pass_names = list(models_meta["pass"]["feature_names"])
            self._hand_indices["pass"] = np.array([name_to_idx[n] for n in pass_names])
        else:
            self._needs_full_state = False

        if not skip_behavioral_check:
            # Match _select_state: pass None for partner_feature_names when
            # _needs_full_state so extract_state_features returns all 69 features
            sanity_partner = (
                None if self._needs_full_state else self._partner_feature_names
            )
            _check_gbt_predictions_sane(
                self.gbt_models,
                sanity_partner,
                include_positional=self._has_positional or self._needs_full_state,
                hand_indices=self._hand_indices if not self._has_positional else None,
                has_moon_loner=self._has_moon_loner,
            )

    def _select_state(
        self, obs: BiddingObservation, family: str, trump_suit: Optional[str]
    ) -> np.ndarray:
        """Extract state features, selecting the appropriate subset for the model."""
        contract_family = family if family != "pass" else "none"
        state = extract_state_features(
            obs,
            contract_family,
            trump_suit,
            partner_feature_names=(
                None if self._needs_full_state else self._partner_feature_names
            ),
            include_positional=self._has_positional or self._needs_full_state,
        )
        if not self._has_positional and family in self._hand_indices:
            state = state[self._hand_indices[family]]
        return state

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        """Select the legal action with highest predicted E[net_points]."""
        legal = enumerate_legal_actions(obs, include_moon_loner=self._has_moon_loner)

        best_value = float("-inf")
        best_action = BidAction.pass_bid()

        for action in legal:
            if action.is_pass():
                state = self._select_state(obs, "pass", None)
                if self._has_interactions:
                    interactions = compute_interaction_features(state)
                    state = np.concatenate([state, interactions])
                value = float(self.pass_gbt.predict(state.reshape(1, -1))[0])
            else:
                contract_type, trump_suit = action.to_contract_tuple()
                family = contract_type
                state = self._select_state(obs, family, trump_suit)
                if self._has_interactions:
                    interactions = compute_interaction_features(state)
                    state = np.concatenate([state, interactions])
                action_feats = extract_action_features(
                    action.n,
                    action.bid_type,
                    include_moon_loner=self._has_moon_loner,
                )
                features = np.concatenate([state, action_feats])
                value = float(
                    self.gbt_models[family].predict(features.reshape(1, -1))[0]
                )

            if value > best_value:
                best_value = value
                best_action = action

        return best_action


def _would_overbid_cap(obs: BiddingObservation, raw: BidAction) -> bool:
    """Enhancement A v2 predicate: dealer +1 overbid cap.

    Returns True when:
    1. There is a standing bid (current_high_bid > 0).
    2. The raw bid is a regular bid (not moon/loner — those are always
       allowed regardless of the current high bid).
    3. The raw bid level exceeds current_high_bid + 1.

    When all three hold, the caller should cap the bid to
    ``current_high_bid + 1`` in the same contract, rather than passing.

    Note: the caller ensures this is only invoked for the dealer seat.
    Moon/loner bids are exempt — they represent high-confidence all-or-nothing
    commitments that the cap should not restrict.
    """
    # All-pass auction (no high bid) — nothing to cap against.
    if obs.current_high_bid <= 0:
        return False

    # Moon/loner bids are exempt from the cap.
    if raw.bid_type in {"moon", "loner"}:
        return False

    return raw.n > obs.current_high_bid + 1


def _partner_is_high_bidder(obs: BiddingObservation) -> bool:
    """Check whether the dealer's partner currently holds the high bid.

    Scans the auction transcript for the last BID entry; returns True when
    that entry's seat is the partner of ``obs.seat`` (i.e. ``(seat + 2) % 4``).

    Returns False when there is no standing bid (all-pass auction) or the
    high bidder is an opponent or the dealer themselves.

    This is unconditional — the dealer should *never* overbid their own
    partner, regardless of Enhancement A/B flag state.
    """
    if obs.current_high_bid <= 0:
        return False

    partner_seat = (obs.seat + 2) % 4
    # Walk the transcript to find the last BID entry.
    last_bidder_seat: int | None = None
    for entry in obs.auction_transcript:
        if entry.get("action") == "BID":
            last_bidder_seat = entry.get("seat")

    return last_bidder_seat == partner_seat


def _would_nudge_partner(obs: BiddingObservation, raw: BidAction) -> bool:
    """Enhancement B predicate: detect +1 same-suit bump of partner's bid.

    Returns True when:
    1. The raw action is a regular suit bid (not moon/loner, not HIGH/LOW).
    2. Partner has bid in the same suit.
    3. The raw bid is exactly partner's tricks + 1 in that suit.
    4. We are the dealer (last bidder).

    This targets the lazy "+1 nudge" failure mode where the model bumps
    partner's already-committed suit contract by the minimum increment.
    """
    if raw.bid_type != "regular":
        return False
    if raw.contract not in {"C", "D", "H", "S"}:
        return False

    # Find the most recent BID from partner.
    partner_seat = (obs.seat + 2) % 4
    partner_bid: dict | None = None
    for entry in obs.auction_transcript:
        if entry.get("action") != "BID":
            continue
        if entry.get("seat") != partner_seat:
            continue
        partner_bid = entry  # last write wins — transcripts are time-ordered

    if partner_bid is None:
        return False
    if partner_bid.get("contract_type") != "suit":
        return False
    if partner_bid.get("trump") != raw.contract:
        return False

    # Same-suit bump: fire only on the exact +1 nudge.
    if raw.n != partner_bid.get("tricks_bid", -99) + 1:
        return False

    # Only fires when we are the dealer (last bidder).
    return obs.seat == obs.dealer_seat


class FilteredGBTBidder(BiddingPolicy):
    """Wrapper around GBTActionValueBidder with post-inference filters.

    Applies independently togglable behavioural filters after the inner
    bidder produces a raw action:

    - **flag_a** (Enhancement A — v2): Cap dealer bids to at most
      ``current_high_bid + 1`` for regular bids.  Moon/loner bids are
      exempt from the cap.
    - **flag_b** (Enhancement B): Suppress same-suit +1 nudge of partner's
      bid when the dealer is the last bidder.

    Both filters only fire when the current seat is the dealer (last
    bidder in LOD auction order).

    Construction modes:
    - Direct: ``FilteredGBTBidder(inner=gbt_bidder, flag_a=True)``
    - From YAML config: ``FilteredGBTBidder(artifact_path="...", flag_a=True)``
      — constructs the inner GBTActionValueBidder automatically.
    """

    VERSION = ARTIFACT_BIDDER_VERSION

    def __init__(
        self,
        inner: Optional[GBTActionValueBidder] = None,
        flag_a: bool = True,
        flag_b: bool = False,
        name: str = "filtered_gbt_action_value",
        *,
        artifact_path: Optional[str] = None,
    ):
        super().__init__(name=name)

        if inner is not None and artifact_path is not None:
            raise ValueError("Specify either 'inner' or 'artifact_path', not both")
        if inner is None and artifact_path is None:
            raise ValueError(
                "FilteredGBTBidder requires either 'inner' (GBTActionValueBidder) "
                "or 'artifact_path' to construct one"
            )

        if inner is not None:
            self._inner = inner
        else:
            assert artifact_path is not None  # for type narrowing
            self._inner = GBTActionValueBidder(
                artifact_path=artifact_path, name=f"{name}_inner"
            )

        self._flag_a = flag_a
        self._flag_b = flag_b

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        """Select action via inner bidder, then apply post-inference filters."""
        raw = self._inner.choose_bid(obs)

        # Pass-through: the inner bidder already chose to pass.
        if raw.is_pass():
            return raw

        # Filters only apply to the dealer (last bidder in auction order).
        if obs.seat != obs.dealer_seat:
            return raw

        # Unconditional partner-awareness: never overbid your own partner.
        # This fires before Enhancement A/B — if partner holds the high bid,
        # the dealer always passes regardless of the model's evaluation.
        if _partner_is_high_bidder(obs):
            return BidAction.pass_bid()

        if self._flag_a and _would_overbid_cap(obs, raw):
            # Cap the bid to current_high_bid + 1, keeping the same contract.
            # Do NOT return early — the capped bid must still be evaluated
            # against flag-B (it could be a same-suit +1 nudge of partner).
            raw = BidAction.bid(obs.current_high_bid + 1, raw.contract)

        if self._flag_b and _would_nudge_partner(obs, raw):
            return BidAction.pass_bid()

        return raw


def predict_logistic(model_dict: dict, features: np.ndarray) -> float:
    """Sigmoid prediction from a logistic model dict.

    Each model_dict has "coefficients" (array) and "intercept" (float).
    Returns P(positive class) = 1 / (1 + exp(-(features @ coef + intercept))).
    """
    coefficients = np.asarray(model_dict["coefficients"], dtype=np.float64)
    intercept = float(model_dict.get("intercept", 0.0))
    logit = float(np.dot(coefficients, features) + intercept)
    # Clip logit to avoid overflow in exp
    logit = max(min(logit, 500.0), -500.0)
    return 1.0 / (1.0 + math.exp(-logit))


class TwoStageActionValueBidder(BiddingPolicy):
    """Two-stage action-value bidder with explicit make/set decomposition.

    For suit bids: uses P(make) logistic + conditional payoff OLS models.
    For high/low/pass: uses standard OLS (same as ActionValueBidder).

    Artifact schema: two_stage_action_value_v1
    """

    VERSION = ARTIFACT_BIDDER_VERSION

    def __init__(
        self,
        artifact_path: str,
        name: str = "two_stage_action_value",
        skip_behavioral_check: bool = False,
    ):
        super().__init__(name=name)

        with open(artifact_path) as f:
            artifact = json.load(f)

        schema = artifact.get("schema_version")
        if schema != "two_stage_action_value_v1":
            raise ValueError(
                f"Expected schema_version 'two_stage_action_value_v1', got '{schema}'"
            )

        # Reject quarantined artifacts
        status = artifact.get("status", "active")
        if status == "quarantined":
            raise ValueError(
                f"Artifact is quarantined (status='quarantined'): {artifact_path}"
            )

        models = artifact["models"]

        # Suit model: three-component structure
        suit = models["suit"]
        self.suit_logistic = suit["logistic"]
        self.suit_make_model = suit["make_model"]
        self.suit_set_model = suit["set_model"]

        # R² quality warning for high/low
        for family in ("high", "low"):
            r2 = models[family].get("r_squared")
            if r2 is not None and r2 < _R2_WARNING_THRESHOLD:
                logger.warning(
                    "Low R² for %s model: %.4f < %.2f — possible wrong-target "
                    "or stale artifact: %s",
                    family,
                    r2,
                    _R2_WARNING_THRESHOLD,
                    artifact_path,
                )

        # High/low use standard OLS format
        self.models = {
            "high": models["high"],
            "low": models["low"],
        }
        self.pass_model = models["pass"]
        self.context_features = artifact.get("metadata", {}).get("context_features", [])

        # Detect interaction feature set from artifact metadata
        feature_set = artifact.get("feature_set", "full")
        self._has_interactions = feature_set == "interaction"

        # Artifact-driven feature validation
        # Two-stage suit model stores feature_names at top level of suit result
        suit_feature_names = suit.get("feature_names")
        if suit_feature_names is None:
            raise ValueError("Artifact suit model missing required 'feature_names'")
        self._partner_feature_names, self._has_positional = _validate_artifact_features(
            list(suit_feature_names),
            self._has_interactions,
        )
        for family in ("high", "low"):
            model = self.models[family]
            if "feature_names" not in model:
                raise ValueError(
                    f"Artifact {family} model missing required 'feature_names'"
                )
            partner_check, pos_check = _validate_artifact_features(
                list(model["feature_names"]),
                self._has_interactions,
            )
            if partner_check != self._partner_feature_names:
                raise ValueError(
                    f"Artifact {family} model has different partner features than suit: "
                    f"{partner_check} vs {self._partner_feature_names}"
                )
        if "feature_names" not in self.pass_model:
            raise ValueError("Artifact pass model missing required 'feature_names'")
        _validate_pass_model_features(
            list(self.pass_model["feature_names"]),
            self._partner_feature_names,
            self._has_interactions,
            has_positional=self._has_positional,
        )

        # Detect whether artifact uses 4 (moon/loner) or 2 (base) action features.
        # Must be computed UNCONDITIONALLY — R3 models have positional=True AND
        # moon/loner features.
        self._has_moon_loner = _detect_action_feature_count(
            list(suit_feature_names)
        ) == len(ACTION_FEATURE_NAMES)

        # For R0/selected models: precompute per-family hand feature indices.
        # R1 forward-selected artifacts may include partner/position features
        # that are not in _HAND_FEATURE_NAMES — use STATE_FEATURE_NAMES when needed.
        self._hand_indices: dict[str, Optional[np.ndarray]] = {}
        hand_name_set = set(_HAND_FEATURE_NAMES)
        if not self._has_positional:
            n_action = _detect_action_feature_count(list(suit_feature_names))
            # Suit model: feature_names at top level of suit result
            all_state_names: list[str] = list(suit_feature_names[:-(n_action)])
            for family in ("high", "low"):
                all_state_names.extend(
                    self.models[family]["feature_names"][:-(n_action)]
                )
            all_state_names.extend(self.pass_model["feature_names"])
            self._needs_full_state = any(
                n not in hand_name_set for n in all_state_names
            )

            if self._needs_full_state:
                name_to_idx = {n: i for i, n in enumerate(STATE_FEATURE_NAMES)}
            else:
                name_to_idx = {n: i for i, n in enumerate(_HAND_FEATURE_NAMES)}

            suit_state_names = suit_feature_names[:-(n_action)]
            self._hand_indices["suit"] = np.array(
                [name_to_idx[n] for n in suit_state_names]
            )
            for family in ("high", "low"):
                state_names = self.models[family]["feature_names"][:-(n_action)]
                self._hand_indices[family] = np.array(
                    [name_to_idx[n] for n in state_names]
                )
            pass_names = list(self.pass_model["feature_names"])
            self._hand_indices["pass"] = np.array([name_to_idx[n] for n in pass_names])
        else:
            self._needs_full_state = False

    def _select_state(
        self, obs: BiddingObservation, family: str, trump_suit: Optional[str]
    ) -> np.ndarray:
        """Extract state features, selecting the appropriate subset for the model."""
        contract_family = family if family != "pass" else "none"
        state = extract_state_features(
            obs,
            contract_family,
            trump_suit,
            partner_feature_names=(
                None if self._needs_full_state else self._partner_feature_names
            ),
            include_positional=self._has_positional or self._needs_full_state,
        )
        if not self._has_positional and family in self._hand_indices:
            state = state[self._hand_indices[family]]
        return state

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        """Select the legal action with highest predicted E[net_points]."""
        legal = enumerate_legal_actions(obs, include_moon_loner=self._has_moon_loner)

        best_value = float("-inf")
        best_action = BidAction.pass_bid()

        for action in legal:
            if action.is_pass():
                # Pass model: state-only features with "none" contract encoding
                state = self._select_state(obs, "pass", None)
                if self._has_interactions:
                    interactions = compute_interaction_features(state)
                    state = np.concatenate([state, interactions])
                value = predict_ols(self.pass_model, state)
            else:
                contract_type, trump_suit = action.to_contract_tuple()
                family = contract_type  # "suit", "high", or "low"
                state = self._select_state(obs, family, trump_suit)
                if self._has_interactions:
                    interactions = compute_interaction_features(state)
                    state = np.concatenate([state, interactions])
                action_feats = extract_action_features(
                    action.n,
                    action.bid_type,
                    include_moon_loner=self._has_moon_loner,
                )
                features = np.concatenate([state, action_feats])

                if family == "suit":
                    # Two-stage: P(make)*E[pts|make] + (1-P(make))*E[pts|set]
                    p_make = predict_logistic(self.suit_logistic, features)
                    e_make = predict_ols(self.suit_make_model, features)
                    e_set = predict_ols(self.suit_set_model, features)
                    value = p_make * e_make + (1.0 - p_make) * e_set
                else:
                    # High/low: standard OLS
                    value = predict_ols(self.models[family], features)

            if value > best_value:
                best_value = value
                best_action = action

        return best_action
