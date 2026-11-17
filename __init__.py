def classFactory(iface):
    from .plugin import CalePlanPlugin
    return CalePlanPlugin(iface)
