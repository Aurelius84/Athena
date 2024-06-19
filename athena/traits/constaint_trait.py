import athena.ir.ir_constraint as ir_constraint
import typing as t
from collections import OrderedDict

class ConstraintAttr:

  def add_eq_cstr(self, lhs, rhs):
    if lhs == rhs:
      return
    cstr = ir_constraint.EqualConstraint(lhs, rhs)
    self.get_eq_cstrs().append(cstr)

  def add_broadcastable_cstr(self, lhs, rhs):
    if lhs == rhs:
      return
    cstr = ir_constraint.BroadcastableConstraint(lhs, rhs)
    self.get_broadcastable_cstrs().append(cstr)

  def add_gt_one_cstr(self, dim_expr):
    cstr = ir_constraint.GtOneConstraint(dim_expr)
    self.get_gt_one_cstrs().append(cstr)

  def get_eq_cstrs(self):
    if not hasattr(self, 'eq_cstrs_'):
      self.eq_cstrs_ = []
    return self.eq_cstrs_

  def get_broadcastable_cstrs(self):
    if not hasattr(self, 'broadcastable_cstrs_'):
      self.broadcastable_cstrs_ = []
    return self.broadcastable_cstrs_

  def get_gt_one_cstrs(self):
    if not hasattr(self, 'one_cstrs_'):
      self.one_cstrs_ = []
    return self.one_cstrs_

  def MakeConstraintManager(self):
    def MakePairs(cstrs):
      return [(cstr.lhs, cstr.rhs) for cstr in cstrs]
    return ir_constraint.ConstraintManager(
      eq_cstrs=_MakeFindSets(MakePairs(self.get_eq_cstrs())),
      broadcastable_cstrs=_MakeFindSets(MakePairs(self.get_broadcastable_cstrs())),
      gt_one_cstrs=self.get_gt_one_cstrs(),
    )

def _MakeFindSets(cstrs: t.List[t.Tuple[t.Any, t.Any]]) -> t.List[t.List[t.Any]]:
  node2parent = {}
  for lhs, rhs in cstrs:
    node2parent[rhs] = lhs
  def FindRoot(x):
    if x not in node2parent:
      return x
    return FindRoot(node2parent[x])
  root2clusters = OrderedDict()
  def GetCluster(root):
    if root not in root2clusters:
      root2clusters[root] = OrderedDict({root:True})
    return root2clusters[root]
  for lhs, rhs in cstrs:
    GetCluster(FindRoot(lhs))[lhs] = True
    GetCluster(FindRoot(rhs))[rhs] = True
  return [[x for x in cluster] for root, cluster in root2clusters.items()]