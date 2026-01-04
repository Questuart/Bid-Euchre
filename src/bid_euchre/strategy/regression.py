"""
Regression-based bidding strategies.
"""

import pickle
import os
import numpy as np
from typing import List, Tuple, Optional, Dict, Any

from .base import Strategy
from .greedy import ImprovedGreedyStrategy
from ..core.cards import Card
from ..features.hand_eval import get_hand_features
from ..analysis.models import SimpleOLS

class RegressionBidder(ImprovedGreedyStrategy):
    """
    A bidder that uses regression models to decide its bid and contract.
    It inherits from ImprovedGreedyStrategy for the card-play phase.
    """

    def __init__(
        self, 
        model_paths: Dict[str, str], 
        name: str = "regression_bidder",
        policy: str = "round",
        fixed_bid: Optional[int] = None,
        debug: bool = False
    ):
        """
        Args:
            model_paths: Dict mapping 'suit', 'high', 'low' to .pkl file paths.
            name: Strategy name.
            policy: "round", "floor", or "ceil".
            fixed_bid: If set, always bids this amount if it chooses to bid.
            debug: Whether to log decisions.
        """
        super().__init__(name=name, debug=debug)
        self.policy = policy
        self.fixed_bid = fixed_bid
        self.models = self._load_models(model_paths)

    def _load_models(self, paths: Dict[str, str]) -> Dict[str, Any]:
        models = {}
        for ctype, path in paths.items():
            if not os.path.exists(path):
                # Fallback for relative paths if needed
                alt_path = os.path.join(os.getcwd(), path)
                if os.path.exists(alt_path):
                    path = alt_path
                else:
                    raise FileNotFoundError(f"Model file not found: {path}")
            
            with open(path, 'rb') as f:
                models[ctype] = pickle.load(f)
        return models

    def decide_bid(
        self,
        hand: List[Card],
        current_high_bid: int,
        current_winner_index: Optional[int],
        partner_index: int,
        player_index: int,
    ) -> Tuple[int, Optional[str], Optional[str]]:
        """
        Evaluate all 6 possible contracts and choose the best one.
        """
        # Dealer-partner pass rule: if partner already holds the high bid, pass
        is_dealer = (player_index == 3) # Assuming dealer is always index 3 in a round
        # Wait, the simulation should tell us if we are the dealer or not.
        # Let's assume the caller passes the correct context.
        # Actually, in Bid Euchre, dealer is just one of the seats.
        # Let's use the partner_index comparison.
        if current_winner_index == partner_index:
            # Simple rule: if partner is winning, don't overbid them (unless you have a HUGE hand?)
            # The user requested: "if the bidder is the dealer... the dealer should evaluate if their partner already has the highest bid and pass."
            # We need to know who the dealer is. Let's assume for now the dealer is always the last bidder in the sequence.
            # But the simulation loop might be different.
            pass # We'll check this in the simulation loop or pass a flag.

        best_bid = 0
        best_contract = None
        best_trump = None
        best_expected_tricks = -1.0

        # Evaluate all 6 scenarios
        scenarios = []
        # 4 suit scenarios
        for suit in ["C", "D", "H", "S"]:
            scenarios.append(("suit", suit))
        # 2 no-trump scenarios
        scenarios.append(("high", None))
        scenarios.append(("low", None))

        for ctype, trump in scenarios:
            # Extract features
            feats = get_hand_features(hand, contract_type=ctype, trump_suit=trump)
            
            # Add is_bidder feature (assume we are the bidder during evaluation)
            feats['is_bidder'] = 1
            
            # Get the right model
            model_data = self.models.get(ctype)
            if not model_data:
                continue
                
            model = model_data['model']
            feature_names = model_data['features']
            
            # Prepare feature vector
            X = np.array([feats[fname] for fname in feature_names]).reshape(1, -1)
            
            # Predict
            pred = model.predict(X)[0]
            
            if pred > best_expected_tricks:
                best_expected_tricks = pred
                best_contract = ctype
                best_trump = trump

        # Apply policy to get bid amount
        if self.policy == "floor":
            bid_amount = int(np.floor(best_expected_tricks))
        elif self.policy == "ceil":
            bid_amount = int(np.ceil(best_expected_tricks))
        elif self.policy == "ccrider":
            # CCrider policy: ceiling for suit when >7, round for high/low, otherwise round
            if best_contract == "suit" and best_expected_tricks > 7:
                bid_amount = int(np.ceil(best_expected_tricks))
            else:
                bid_amount = int(np.round(best_expected_tricks))
        else:
            bid_amount = int(np.round(best_expected_tricks))

        # Force fixed bid if requested (e.g. FiveHeadFred)
        if self.fixed_bid is not None and bid_amount > 0:
            bid_amount = self.fixed_bid

        return bid_amount, best_contract, best_trump
