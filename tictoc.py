
class TicToc(object):
    ''' Simple timer class with an intuitive tic/toc clock-like interface
        Author mnoble@broadinstitute.org '''

    def __init__(self, verbose=True, incremental=False, prefix="TicToc: "):
        ''' Start ticking '''
        import time
        self.timer = time.time
        self.verbose = verbose
        self.timestamp = self.timer()
        self.incremental = incremental
        self.prefix = prefix

    def tic(self):
        ''' Reset timer back to zero, then begin ticking again '''
        self.timestamp = self.timer()

    def toc(self, message=""):
        ''' Report time elapsed since timer last started ticking '''

        elapsed = self.timer() - self.timestamp
        if self.verbose:
            print self.prefix + message + " %6.3f sec" % elapsed

        # Incremental mode makes it clean/simple to report elapsed time between
        # toc() calls, with no ugly/repetive math (or extra variables) in caller
        if self.incremental:
            self.timestamp = self.timer()

        return elapsed
