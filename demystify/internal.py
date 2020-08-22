# This files includes all code which needs to actually call the SMT solver

import copy
import types
import random

from .utils import flatten, chainlist

from .base import EqVal, NeqVal

from .config import CONFIG

# A variable is a dictionary mapping values to their SAT variable

from .solvers.z3impl import Z3Solver
from .solvers.pysatimpl import SATSolver


class Solver:
    def __init__(self, puzzle):
        self._puzzle = puzzle
        if CONFIG["solver"] == "z3":
            self._solver = Z3Solver()
        else:
            self._solver = SATSolver()

        # We want a reliable random source
        self.random = random.Random(1)

        # Map from internal booleans to constraints and vice versa
        self._conmap = {}
        self._conlit2conmap = {}

        # Quick access to every internal boolean which represents a constraint
        self._conlits = set()

        # Set up variable mappings -- we make a bunch as we need these to be fast.
        # 'lit' refers to base.EqVal and base.NeqVar, objects which users should see.
        # 'demystify' refers to the solver's internal representation

        # Map EqVal and NeqVal to internal variables
        self._varlit2smtmap = {}

        # Map internal to EqVal
        self._varsmt2litmap = {}

        # Map internal to a NeqVal (for when they are False in the model)
        self._varsmt2neglitmap = {}

        # Set, so we quickly know is an internal variable represents a variable
        self._varsmt = set([])

        for mat in self._puzzle.vars():
            for v in mat.varlist():
                for d in v.dom():
                    lit = EqVal(v, d)
                    neglit = NeqVal(v, d)
                    b = self._solver.Bool(str(lit))

                    self._varlit2smtmap[lit] = b
                    self._varlit2smtmap[neglit] = self._solver.negate(b)
                    self._varsmt2litmap[b] = lit
                    self._varsmt2neglitmap[b] = neglit
                    self._varsmt.add(b)

        # Unique identifier for each introduced variable
        count = 0

        for mat in puzzle.vars():
            for c in mat.constraints():
                name = "{}{}".format(mat.varname, count)
                count = count + 1
                var = self._solver.Bool(name)
                self._solver.addImplies(var, self._buildConstraint(c))
                self._conmap[var] = c
                assert c not in self._conlit2conmap
                self._conlit2conmap[c] = var
                self._conlits.add(var)

        self._solver.set_phases(positive=self._varsmt, negative=self._conlits)

        count = 0
        for c in self._puzzle.constraints():
            name = "con{}".format(count)
            count = count + 1
            var = self._solver.Bool(name)
            self._solver.addImplies(var, self._buildConstraint(c))
            self._conmap[var] = c
            assert c not in self._conlit2conmap
            self._conlit2conmap[c] = var
            self._conlits.add(var)

        # Used for tracking in push/pop/addLits
        self._stackknownlits = []
        self._knownlits = []

        # For benchmarking
        self._corecount = 0

        self.init_litmappings()

    def init_litmappings(self):
        # Set up some mappings for efficient finding of tiny MUSes
        # Map from a var lit to all the constraints it is in
        self._varlit2con = {l: set() for l in self._varlit2smtmap.keys()}

        # Map from a var lit to the negation of all lits it is in a constraint with
        # (to later make distance 2 mappings)
        self._varlit2negconnectedlits = {l: set() for l in self._varlit2smtmap.keys()}

        for (cvar, con) in self._conmap.items():
            lits = con.lits()
            # Negate all the lits
            neglits = [l.neg() for l in lits]
            for l in neglits:
                self._varlit2con[l].add(cvar)
                self._varlit2negconnectedlits[l].update(neglits)

        # Map from a var lit to all constraints it is distance 2 from
        self._varlit2con2 = {}  # {l : set() for l in self._varlit2smtmap.keys() }
        for (lit, connected) in self._varlit2negconnectedlits.items():
            allcon = set.union(*[self._varlit2con[x] for x in connected]).union(
                self._varlit2con[lit]
            )
            self._varlit2con2[lit] = allcon

    def puzzle(self):
        return self._puzzle

    def _buildConstraint(self, constraint):
        cs = constraint.clauseset()
        clauses = [self._solver.Or([self._varlit2smtmap[lit] for lit in c]) for c in cs]
        return clauses

    # Check if there is a single solution, or return 'None'
    def _solve(self, smtassume=tuple(), *, getsol):
        return self._solver.solve(chainlist(self._conlits, smtassume), getsol=getsol)

    # Check if there is a single solution and return True/False, or return 'None' if timeout
    def _solveLimited(self, smtassume=tuple()):
        return self._solver.solveLimited(chainlist(self._conlits, smtassume))

    # Check if there is a single solution, or return 'None'
    def _solveSingle(self, smtassume=tuple()):
        return self._solver.solveSingle(
            self._varsmt, chainlist(self._conlits, smtassume)
        )

    Multiple = "Multiple"

    def var_smt2lits(self, model):
        ret = []
        for l in self._varsmt:
            if model[l]:
                ret.append(self._varsmt2litmap[l])
            else:
                ret.append(self._varsmt2neglitmap[l])
        return ret

    def solve(self, assume=tuple(), *, getsol):
        smtassume = [self._varlit2smtmap[l] for l in assume]
        sol = self._solve(smtassume, getsol=getsol)
        if getsol == False:
            return sol

        if sol is None:
            return None
        else:
            return self.var_smt2lits(sol)

    # This is the same as 'solve', but checks if there are many solutions,
    # returning Solver.Multiple if there is more than one solution
    def solveSingle(self, assume=tuple()):
        smtassume = [self._varlit2smtmap[l] for l in assume]
        sol = self._solveSingle(smtassume)
        if sol is None:
            return None
        elif sol == self.Multiple:
            return self.Multiple
        else:
            return self.var_smt2lits(sol)

    # Return a subset of 'lits' which forms a core, or
    # None if no core exists (or can be proved in the time limit)
    def basicCore(self, lits):
        self._corecount += 1
        solve = self._solver.solveLimited(lits)
        if solve is True or solve is None:
            return None
        if CONFIG["useUnsatCores"]:
            core = self._solver.unsat_core()
            assert set(core).issubset(set(lits))
        else:
            core = lits
        return core

    def addLit(self, lit):
        self._solver.addLit(self._varlit2smtmap[lit])
        self._knownlits.append(lit)

    def getKnownLits(self):
        return self._knownlits

    def getCurrentDomain(self):
        return self._puzzle.modelToAssignment(self.getKnownLits(), partial=True)

    # Storing and restoring assignments
    def push(self):
        self._solver.push()
        self._stackknownlits.append(copy.deepcopy(self._knownlits))

    def pop(self):
        self._solver.pop()
        self._knownlits = self._stackknownlits.pop()

    def explain(self, c):
        return c.explain(self._knownlits)