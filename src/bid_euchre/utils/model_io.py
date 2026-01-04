"""Standard model I/O operations with validation.

This module provides consistent model saving and loading across the project,
preventing format inconsistencies and ensuring backward compatibility.

Usage:
    from bid_euchre.utils import save_model, load_model
    
    # Saving a model
    save_model(
        model=my_ols_model,
        features=['trump_count', 'is_bidder'],
        contract_type='suit',
        path='data/models/current/my_model/suit.pkl'
    )
    
    # Loading a model
    model_data = load_model('data/models/current/my_model/suit.pkl')
    model = model_data['model']
    features = model_data['features']
"""

import pickle
import os
from typing import Any, List, Dict, Optional
from datetime import datetime


CURRENT_SCHEMA_VERSION = 1


def save_model(
    model: Any,
    features: List[str],
    contract_type: str,
    path: str,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """Save a model in standard format with validation.
    
    Args:
        model: The trained model object (e.g., SimpleOLS, SimpleRidge)
        features: List of feature names in order
        contract_type: 'suit', 'high', or 'low'
        path: Full path where to save the model (.pkl file)
        metadata: Optional additional metadata to store
        
    Raises:
        ValueError: If contract_type is invalid or features list is empty
        OSError: If path directory doesn't exist
    """
    # Validate inputs
    if contract_type not in ('suit', 'high', 'low'):
        raise ValueError(f"contract_type must be 'suit', 'high', or 'low', got: {contract_type}")
    
    if not features:
        raise ValueError("features list cannot be empty")
    
    if not hasattr(model, 'predict'):
        raise ValueError("model must have a 'predict' method")
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    # Create standard model dictionary
    model_dict = {
        'model': model,
        'features': features,
        'contract_type': contract_type,
        'schema_version': CURRENT_SCHEMA_VERSION,
        'saved_at': datetime.now().isoformat(),
    }
    
    # Add optional metadata
    if metadata:
        model_dict['metadata'] = metadata
    
    # Save
    with open(path, 'wb') as f:
        pickle.dump(model_dict, f)
    
    print(f"✅ Saved model: {path}")
    print(f"   Contract: {contract_type}, Features: {len(features)}")


def load_model(path: str, validate: bool = True) -> Dict[str, Any]:
    """Load a model with format validation.
    
    Args:
        path: Path to the .pkl model file
        validate: Whether to validate the loaded model format
        
    Returns:
        Dictionary containing:
            - 'model': The model object
            - 'features': List of feature names
            - 'contract_type': Contract type string
            - 'schema_version': Format version (if present)
            - Other metadata fields
            
    Raises:
        FileNotFoundError: If model file doesn't exist
        ValueError: If model format is invalid (when validate=True)
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Model file not found: {path}")
    
    with open(path, 'rb') as f:
        model_data = pickle.load(f)
    
    # Handle legacy format (raw model object)
    if not isinstance(model_data, dict):
        print(f"⚠️  Warning: Loading legacy model format from {path}")
        print("   Consider retraining with save_model() for standard format")
        return {
            'model': model_data,
            'features': None,  # Unknown
            'contract_type': None,  # Unknown
            'schema_version': 0,  # Legacy
        }
    
    # Validate standard format
    if validate:
        required_fields = ['model', 'features', 'contract_type']
        missing = [f for f in required_fields if f not in model_data]
        if missing:
            raise ValueError(f"Invalid model format, missing fields: {missing}")
        
        if not hasattr(model_data['model'], 'predict'):
            raise ValueError("Loaded model missing 'predict' method")
    
    return model_data


def migrate_legacy_model(legacy_path: str, output_path: str, features: List[str], contract_type: str) -> None:
    """Migrate a legacy model (raw pickle) to standard format.
    
    Args:
        legacy_path: Path to legacy model file
        output_path: Where to save the migrated model
        features: Feature list for this model
        contract_type: Contract type for this model
    """
    print(f"Migrating legacy model: {legacy_path}")
    
    with open(legacy_path, 'rb') as f:
        model = pickle.load(f)
    
    save_model(
        model=model,
        features=features,
        contract_type=contract_type,
        path=output_path,
        metadata={'migrated_from': legacy_path}
    )
    
    print(f"✅ Migration complete: {output_path}")
