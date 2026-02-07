from pydantic import BaseModel

# Custom Pydantic Model that behaves like a dict for backward compatibility
class DictModel(BaseModel):
    def __getitem__(self, item):
        try:
            return getattr(self, item)
        except AttributeError:
            raise KeyError(item)
    
    def get(self, item, default=None):
        return getattr(self, item, default)

    def __setitem__(self, key, value):
        setattr(self, key, value)
    
    def __contains__(self, item):
        return hasattr(self, item)
