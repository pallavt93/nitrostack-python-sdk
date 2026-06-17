from typing import Any, Dict, List, Type, Union

class DIContainer:
    _instance = None

    @classmethod
    def get_instance(cls) -> "DIContainer":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton container (useful for testing)."""
        cls._instance = None

    def __init__(self):
        self._registry: Dict[Any, Type] = {}
        self._instances: Dict[Any, Any] = {}

    def register(self, cls: Type) -> None:
        """Register a provider class."""
        self._registry[cls] = cls

    def register_value(self, token: Any, value: Any) -> None:
        """Register a constant value or instantiated service with a token."""
        self._instances[token] = value
        # Also map token to its type if possible
        if not isinstance(token, str):
            self._registry[token] = type(value)

    def resolve(self, token: Any) -> Any:
        """
        Resolve a dependency by token (class type or string key).
        Instantiates classes if not already instantiated.
        """
        # 1. Check if we already have a cached instance
        if token in self._instances:
            return self._instances[token]

        # 2. Check if the token is registered as a class
        cls = self._registry.get(token)
        
        # 3. If not registered, but it's a class type, check if it's decorated with @injectable
        if cls is None and isinstance(token, type):
            cls = token
            # We auto-register it to make usage easier
            self.register(cls)

        from nitrostack.core.errors import DependencyResolutionError

        if cls is None:
            raise DependencyResolutionError(f"Dependency '{token}' is not registered in the DIContainer.")

        # 4. Resolve dependencies of the class
        deps = getattr(cls, "_mcp_deps", [])
        resolved_args = []
        for dep in deps:
            resolved_args.append(self.resolve(dep))

        # 5. Instantiate the class
        try:
            instance = cls(*resolved_args)
        except Exception as e:
            raise DependencyResolutionError(f"Failed to instantiate class '{cls.__name__}' due to: {e}") from e

        # 6. Cache and return the singleton instance
        self._instances[token] = instance
        return instance

def injectable(deps: List[Any] = None):
    """
    Decorator to mark a class as Injectable.
    Requires explicit list of dependencies.
    """
    if deps is None:
        deps = []
    def decorator(cls: Type):
        cls._mcp_deps = deps
        # Automatically register with the DIContainer
        DIContainer.get_instance().register(cls)
        return cls
    return decorator
