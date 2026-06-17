from dataclasses import dataclass, field
from typing import List, Type, Optional

@dataclass
class ModuleConfig:
    name: str
    controllers: List[Type] = field(default_factory=list)
    providers: List[Type] = field(default_factory=list)
    imports: List[Type] = field(default_factory=list)
    exports: List[Type] = field(default_factory=list)

def module(
    name: str,
    controllers: Optional[List[Type]] = None,
    providers: Optional[List[Type]] = None,
    imports: Optional[List[Type]] = None,
    exports: Optional[List[Type]] = None,
):
    """
    Decorator to define a Module.
    Groups controllers, providers, imports, and exports.
    """
    if controllers is None:
        controllers = []
    if providers is None:
        providers = []
    if imports is None:
        imports = []
    if exports is None:
        exports = []

    def decorator(cls: Type):
        config = ModuleConfig(
            name=name,
            controllers=controllers,
            providers=providers,
            imports=imports,
            exports=exports
        )
        cls._mcp_module_config = config
        return cls
    return decorator
