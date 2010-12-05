# -*- coding: utf-8 -*-
# Spyder's ExternalPythonShell sitecustomize

import sys, os, os.path as osp

# Prepending this spyderlib package's path to sys.path to be sure 
# that another version of spyderlib won't be imported instead:
spyderlib_path = osp.dirname(__file__)
while not osp.isdir(osp.join(spyderlib_path, 'spyderlib')):
    spyderlib_path = osp.abspath(osp.join(spyderlib_path, os.pardir))
if not spyderlib_path.startswith(sys.prefix):
    # Spyder is not installed: moving its parent directory to the top of 
    # sys.path to be sure that this spyderlib package will be imported in 
    # the remote process (instead of another installed version of Spyder)
    while spyderlib_path in sys.path:
        sys.path.remove(spyderlib_path)
    sys.path.insert(0, spyderlib_path)
os.environ['SPYDER_PARENT_DIR'] = spyderlib_path

if os.environ.get("MATPLOTLIB_PATCH", "").lower() == "true":
    try:
        from spyderlib import mpl_patch
        mpl_patch.set_backend(os.environ.get("MATPLOTLIB_BACKEND", "Qt4Agg"))
        mpl_patch.apply()
    except ImportError:
        pass

# Removing PyQt4 input hook which is not working well on Windows
if os.environ.get("REMOVE_PYQT_INPUTHOOK", "").lower() == "true":
    from PyQt4.QtCore import pyqtRemoveInputHook
    pyqtRemoveInputHook()

if os.name == 'nt': # Windows platforms
            
    # Setting console encoding (otherwise Python does not recognize encoding)
    try:
        import locale, ctypes
        _t, _cp = locale.getdefaultlocale('LANG')
        try:
            _cp = int(_cp[2:])
            ctypes.windll.kernel32.SetConsoleCP(_cp)
            ctypes.windll.kernel32.SetConsoleOutputCP(_cp)
        except (ValueError, TypeError):
            # Code page number in locale is not valid
            pass
    except ImportError:
        pass
        
    # Workaround for IPython thread issues with win32 comdlg32
    if os.environ.get('IPYTHON', False):
        try:
            import win32gui, win32api
            try:
                win32gui.GetOpenFileNameW(File=win32api.GetSystemDirectory()[:2])
            except win32gui.error:
                # This error is triggered intentionally
                pass
        except ImportError:
            # Unfortunately, pywin32 is not installed...
            pass

# Set standard outputs encoding:
# (otherwise, for example, print u"é" will fail)
encoding = None
try:
    import locale
except ImportError:
    pass
else:
    loc = locale.getdefaultlocale()
    if loc[1]:
        encoding = loc[1]

if encoding is None:
    encoding = "UTF-8"

sys.setdefaultencoding(encoding)
    
try:
    import sitecustomize #@UnusedImport
except ImportError:
    pass

# Communication between ExternalShell and the QProcess
if os.environ.get('SPYDER_SHELL_ID') is None:
    monitor = None
else:
    from spyderlib.widgets.externalshell.monitor import Monitor
    monitor = Monitor("127.0.0.1",
                      int(os.environ['SPYDER_I_PORT']),
                      int(os.environ['SPYDER_N_PORT']),
                      os.environ['SPYDER_SHELL_ID'],
                      float(os.environ['SPYDER_AR_TIMEOUT']),
                      os.environ["SPYDER_AR_STATE"].lower() == "true")
    monitor.start()
    
    # Quite limited feature: notify only when a result is displayed in console
    # (does not notify at every prompt)
    def displayhook(obj):
        sys.__displayhook__(obj)
        monitor.refresh()

    sys.displayhook = displayhook

# Patching pdb
import pdb, bdb
class SpyderPdb(pdb.Pdb):
    def user_return(self, frame, return_value):
        """This function is called when a return trap is set here."""
        #-----Spyder-specific---------------------------------------------------
        # This is useful when debugging in an active interpreter (otherwise,
        # the debugger will stop before reaching the target file)
        if self._wait_for_mainpyfile:
            if (self.mainpyfile != self.canonic(frame.f_code.co_filename)
                or frame.f_lineno<= 0):
                return
            self._wait_for_mainpyfile = 0
        #-----Spyder-specific---------------------------------------------------
        frame.f_locals['__return__'] = return_value
        print >>self.stdout, '--Return--'
        self.interaction(frame, None)
        
    def interaction(self, frame, traceback):
        self.setup(frame, traceback)
        self.notify_spyder(frame) #-----Spyder-specific-------------------------
        self.print_stack_entry(self.stack[self.curindex])
        self.cmdloop()
        self.forget()

    def reset(self):
        bdb.Bdb.reset(self)
        self.forget()
        self.set_spyder_breakpoints() #-----Spyder-specific---------------------
        
    def notify_spyder(self, frame):
        if not frame:
            return
        fname = self.canonic(frame.f_code.co_filename)
        lineno = frame.f_lineno
        if isinstance(fname, basestring) and isinstance(lineno, int):
            if osp.isfile(fname) and monitor is not None:
                monitor.notify_pdb_step(fname, lineno)

    def set_spyder_breakpoints(self):
        self.clear_all_breaks()
        #------Really deleting all breakpoints:
        for bp in bdb.Breakpoint.bpbynumber:
            if bp:
                bp.deleteMe()
        bdb.Breakpoint.next = 1
        bdb.Breakpoint.bplist = {}
        bdb.Breakpoint.bpbynumber = [None]
        #------
        from spyderlib.config import CONF
        CONF.load_from_ini()
        if CONF.get('run', 'breakpoints/enabled', True):
            breakpoints = CONF.get('run', 'breakpoints', {})
            i = 0
            for fname, data in breakpoints.iteritems():
                for linenumber, condition in data:
                    i += 1
                    self.set_break(self.canonic(fname), linenumber,
                                   cond=condition)

pdb.Pdb = SpyderPdb

# Restoring (almost) original sys.path:
# (Note: do not remove spyderlib_path from sys.path because if Spyder has been
#  installed using python setup.py install, then this could remove the 
#  'site-packages' directory from sys.path!)
try:
    sys.path.remove(osp.join(spyderlib_path,
                             "spyderlib", "widgets", "externalshell"))
except ValueError:
    pass

## Restoring original PYTHONPATH
#try:
#    os.environ['PYTHONPATH'] = os.environ['OLD_PYTHONPATH']
#    del os.environ['OLD_PYTHONPATH']
#except KeyError:
#    if os.environ.get('PYTHONPATH') is not None:
#        del os.environ['PYTHONPATH']
