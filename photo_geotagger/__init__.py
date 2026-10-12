def classFactory(iface):
    from .plugin import PhotoGeotaggerPlugin
    return PhotoGeotaggerPlugin(iface)
