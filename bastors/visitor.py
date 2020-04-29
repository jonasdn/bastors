class Visitor:
    """ Basis for implementing a visitor pattern to visit all nodes of the
        structure returned from the Parse module.

        Need to implement visit_Program, visit_If, visit_Print, ...
        """

    def __init__(self, defaultfunc=None):
        self._defaultfunc = defaultfunc

    def visit(self, node):
        """ This method will find the __name__ of the node passed to it and
            call the visit method for that node. If node is a Let namedtuple
            then visit_Let() will be called. """
        method = "visit_" + type(node).__name__
        if self._defaultfunc is None:
            self._defaultfunc = self.generic
        visitor = getattr(self, method, self._defaultfunc)
        return visitor(node)

    def generic(self, node):  # pylint: disable=R0201
        """ Called when no visit method found for node. """
        raise Exception("no visit method defined for %s" % type(node).__name__)
