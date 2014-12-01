class Optimization:

    @classmethod
    def process_function(cls, function):
        raise NotImplementedError()

    @property
    @classmethod
    def name(cls):
        return cls.__name__
