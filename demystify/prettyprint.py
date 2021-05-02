from .utils import flatten, intsqrt, lowsqrt
from .base import EqVal, NeqVal
from sortedcontainers import *


def print_var(f, variable, known, involved, involvedset, classprefix, targets):
    dom = variable.dom()
    # Make table square(ish)
    splitsize = 1
    domsize = len(dom)
    if intsqrt(domsize) is not None:
        splitsize = intsqrt(domsize)
    elif domsize % 2 == 0:
        splitsize = domsize // 2
    else:
        splitsize = lowsqrt(domsize)

    print("<table>", file=f)
    for dsublist in [dom[i : i + splitsize] for i in range(0, len(dom), splitsize)]:
        print("<tr>", end="", file=f)
        for d in dsublist:
            style = []
            poslit = EqVal(variable, d)
            neglit = NeqVal(variable, d)
            if neglit in targets:
                style.append("nit")
            elif poslit in targets:
                style.append("pit")
            # Put this neglit check here, as we want to skip displaying it we already know it is gone
            elif neglit in known:
                style.append("nik")
            elif poslit in involvedset:
                style.append("pii")
            elif neglit in involvedset:
                style.append("nii")

            if poslit in known:
                style.append("pik")
            
            for i, clause in enumerate(involved):
                #print(poslit,"::",neglit,"::",clause)
                if (poslit in flatten(clause)) or (neglit in flatten(clause)):
                    style.append(classprefix + str(i))
            print('<td class="{}">{}</td>'.format(" ".join(style), d), file=f, end="")
        print("</tr>", file=f)
    print("</table>", file=f)


# innerborders adds the class 'inner grid' to a sudoku
def print_matrix(f, matrix, known, involved, involvedset, classprefix, targets, innerborders=None):
    print('<table style="border-collapse: collapse; border: solid 2px">', file=f)
    if innerborders is not None:
        for i in range(0, len(matrix.varmat()), innerborders):
            print(
                '<colgroup style="border:solid 3px">'
                + "".join(["<col>" for _ in range(innerborders)]),
                file=f,
            )

    for rowcount, row in enumerate(matrix.varmat()):
        if innerborders is not None and rowcount % innerborders == 0:
            print('<tbody style="border:solid 3px">', file=f)
        print("<tr>", file=f)
        for cell in row:
            print('<td style="border:solid 1px">', file=f)
            print_var(f, cell, known, involved, involvedset, classprefix, targets)
            print("</td>", file=f)
        print("</tr>", file=f)
    print("</table>", file=f)


# print out we have deduced 'targets' using 'mus'
def print_explanation(f, solver, mus, targets, classprefix):
    vars = solver.puzzle().vars()
    # literals the solve already knows
    known = solver.getKnownLits()
    # literals used in the MUS
    involved = [m.clauseset() for m in flatten(mus)]
    
    for matrix in vars:
        print_matrix(f, matrix, SortedSet(known), involved, SortedSet(flatten(involved)), classprefix, SortedSet(targets), 3)
