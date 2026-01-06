import numpy as np


class SimpleOLS:
    """
    Simple OLS regression implementation using normal equation.
    Shared across training and inference.
    """
    def __init__(self):
        self.coef_ = None
        self.intercept_ = None
    
    def fit(self, X, y):
        """Fit OLS using normal equation."""
        X_with_intercept = np.column_stack([np.ones(len(X)), X])
        XtX = X_with_intercept.T @ X_with_intercept
        Xty = X_with_intercept.T @ y
        beta = np.linalg.solve(XtX, Xty)
        self.intercept_ = beta[0]
        self.coef_ = beta[1:]
        return self
    
    def predict(self, X):
        """Make predictions."""
        return X @ self.coef_ + self.intercept_

class SimpleRidge:
    """
    Simple Ridge regression implementation.
    """
    def __init__(self, alpha=1.0):
        self.alpha = alpha
        self.coef_ = None
        self.intercept_ = None

    def fit(self, X, y):
        n_samples, n_features = X.shape
        X_with_intercept = np.column_stack([np.ones(n_samples), X])
        
        # Identity matrix for regularization (don't regularize intercept)
        I = np.eye(n_features + 1)
        I[0, 0] = 0
        
        XtX = X_with_intercept.T @ X_with_intercept
        Xty = X_with_intercept.T @ y
        
        # Ridge normal equation: (X'X + alpha*I) beta = X'y
        beta = np.linalg.solve(XtX + self.alpha * I, Xty)
        
        self.intercept_ = beta[0]
        self.coef_ = beta[1:]
        return self

    def predict(self, X):
        return X @ self.coef_ + self.intercept_
