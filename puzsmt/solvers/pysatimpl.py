import copy
import logging

from pysat.solvers import Solver
from ..utils import chainlist
from ..config import CONFIG

import pysat
import inspect
import time

#print(inspect.getfile(pysat))

class SATSolver:
    def __init__(self):
        self._solver = Solver(name=CONFIG["solver"], incr=CONFIG["solverIncremental"])
        self._boolcount = 1
        self._boolnames = {}
        self._knownlits = set()
        self._stack = []
        self._clauses = 0

    def Bool(self, name):
        newbool = self._boolcount
        self._boolnames[newbool] = name
        self._boolcount += 1
        return newbool

    def negate(self, var):
        return -var

    def Or(self, lits):
        return list(lits)

    def addConstraint(self, clause):
        self._clauses += 1
        self._solver.add_clause(clause)

    def addImplies(self, var, clauses):
        for c in clauses:
            self._clauses += 1
            self._solver.add_clause(c + [-var])
    
    # SAT assignments look like a list of integers, where:
    # '5' means variable 5 is true
    # '-5' means variable 5 is false
    # We want a map where m[5] is true if 5 is true
    def satassignment2map(self, l):
        return {abs(x): x > 0 for x in l}

    def solve(self, lits,*,getsol):
        start_time = time.time()
        x = self._solver.solve(assumptions=chainlist(lits, self._knownlits))
        end_time = time.time()
        if end_time - start_time > 5:
            logging.info("Long time solve: %s %s", len(lits), end_time - start_time)
        if getsol == False:
            return x
        if x:
            return self.satassignment2map(self._solver.get_model())
        else:
            return None

    def solveLimited(self, lits):
        start_time = time.time()
        if CONFIG["solveLimited"]:
            self._solver.conf_budget(100000)
            x = self._solver.solve_limited(assumptions=chainlist(lits, self._knownlits))
        else:
            x = self._solver.solve(assumptions=chainlist(lits, self._knownlits))
        end_time = time.time()
        if end_time - start_time > 5:
            logging.info("Long time solveLimited: %s %s", len(lits), end_time - start_time)
        return x

    def solveSingle(self, puzlits, lits):
        # We just brute force check all assignments to other variables
        sol = self.solve(lits,getsol=True)
        if sol is None:
            return sol
        for p in puzlits:
            if sol[p]:
                extrasol = self.solve(chainlist(lits, [-p]),getsol=False)
            else:
                extrasol = self.solve(chainlist(lits, [p]),getsol=False)
            if extrasol:
                return "Multiple"
        return sol

    # Returns unsat_core from last solve
    def unsat_core(self):
        core = [x for x in self._solver.get_core() if x not in self._knownlits]
        #logging.info("Core size: %s", len(core))
        return core

    def push(self):
        self._stack.append(copy.deepcopy(self._knownlits))
    
    def pop(self):
        self._knownlits = self._stack.pop()

    def addLit(self, var):
        assert var not in self._knownlits
        self._knownlits.add(var)

    def set_phases(self, positive, negative):
        # TODO: Ignore the positive ones seems to be best
        l =  [-x for x in negative]
        self._solver.set_phases(l)
