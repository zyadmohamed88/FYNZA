"""
plugin_manager.py
-----------------
Provides a dynamic plugin architecture for steganography algorithms.
Allows dropping new algorithms into the `plugins/` directory without altering core logic.
"""
"zizo"

import importlib
import os
import pkgutil
import inspect
from abc import ABC, abstractmethod

import numpy as np


class SteganographyPlugin(ABC):
    """Base class for all steganography plugins."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the algorithm (e.g., 'LSB_Basic', 'Adaptive_Edge')."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Brief description of the algorithm's approach and security properties."""
        pass

    @abstractmethod
    def get_capacity(self, image: np.ndarray) -> int:
        """Return the maximum payload capacity in bytes."""
        pass

    @abstractmethod
    def embed(self, carrier: np.ndarray, payload: bytes) -> np.ndarray:
        """Embed the binary payload into the carrier image."""
        pass

    @abstractmethod
    def extract(self, stego: np.ndarray) -> bytes:
        """Extract the binary payload from the stego image."""
        pass


class PluginManager:
    """Discovers, loads, and manages available steganography plugins."""

    def __init__(self, plugins_package="plugins"):
        self.plugins_package = plugins_package
        self.plugins = {}
        self.load_plugins()

    def load_plugins(self):
        """Dynamically load all modules in the plugins package that inherit from SteganographyPlugin."""
        self.plugins.clear()
        
        # Ensure plugins directory exists
        base_dir = os.path.dirname(os.path.abspath(__file__))
        plugins_dir = os.path.join(base_dir, self.plugins_package)
        if not os.path.exists(plugins_dir):
            os.makedirs(plugins_dir)
            # Create an empty __init__.py
            with open(os.path.join(plugins_dir, "__init__.py"), "w") as f:
                pass

        try:
            package = importlib.import_module(self.plugins_package)
            for _, module_name, _ in pkgutil.iter_modules(package.__path__):
                full_module_name = f"{self.plugins_package}.{module_name}"
                module = importlib.import_module(full_module_name)
                
                # Find classes inheriting from SteganographyPlugin and are not abstract
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, SteganographyPlugin) and 
                        attr is not SteganographyPlugin and
                        not inspect.isabstract(attr)):
                        instance = attr()
                        self.plugins[instance.name.lower()] = instance
        except ImportError as e:
            print(f"Warning: Could not load plugins package. {e}")

    def get_plugin(self, name: str) -> SteganographyPlugin:
        name = name.lower()
        if name not in self.plugins:
            raise ValueError(f"Plugin '{name}' not found. Available: {list(self.plugins.keys())}")
        return self.plugins[name]

    def list_plugins(self) -> dict:
        return {name: plugin.description for name, plugin in self.plugins.items()}

# Global plugin manager instance
manager = PluginManager()
