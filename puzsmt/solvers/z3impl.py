import z3


class Z3Solver:
    def __init__(self):
        self._solver = z3.Solver()


    def Bool(self, name):
        return z3.Bool(name)

    def negate(self, var):
        return z3.Not(var)

    def Or(self, lits):
        return z3.Or(lits)

    def addConstraint(self, clause):
        self._solver.add(clause)

    def addImplies(self, var, clauses):
        # tiny optimisation
        if len(clauses) == 1:
            con = clauses[0]
        else:
            con = z3.And(clauses)
        self._solver.add(z3.Implies(var, con))
    
    def solve(self, lits):
        result = self._solver.check(lits)
        if result == z3.unsat:
            return None
        else:
            return self._solver.model()

    # Returns unsat_core from last solve
    def unsat_core(self):
        return self._solver.unsat_core()

    def push(self):
        self._solver.push()
    
    def pop(self):
        self._solver.pop()

    def addLit(self, var):
        self._solver.add(var)