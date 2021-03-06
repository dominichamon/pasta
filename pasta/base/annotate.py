# coding=utf-8
"""Annotate python syntax trees with formatting from the soruce file."""
# Copyright 2017 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import abc
import ast
import contextlib
import six
from six.moves import zip

from pasta.base import ast_constants
from pasta.base import ast_utils
from pasta.base import token_generator


def parenthesizable(f):
  """Decorates a function where the node visited can be wrapped in parens."""
  @contextlib.wraps(f)
  def wrapped(self, node, *args, **kwargs):
    with self.scope(node):
      self.prefix(node)
      f(self, node, *args, **kwargs)
      self.suffix(node, oneline=True)
  return wrapped


def spaced(f):
  """Decorates a function where the node visited can have space around it."""
  @contextlib.wraps(f)
  def wrapped(self, node, *args, **kwargs):
    self.prefix(node)
    f(self, node, *args, **kwargs)
    self.suffix(node, oneline=True)
  return wrapped


class BaseVisitor(ast.NodeVisitor):
  """Walks a syntax tree in the order it appears in code.

  This class has a dual-purpose. It is implemented (in this file) for annotating
  an AST with formatting information needed to reconstruct the source code, but
  it also is implemented in pasta.base.codegen to reconstruct the source code.

  Each visit method in this class specifies the order in which both child nodes
  and syntax tokens appear, plus where to account for whitespace, commas,
  parentheses, etc.
  """

  __metaclass__ = abc.ABCMeta

  def visit(self, node):
    ast_utils.setup_props(node)
    super(BaseVisitor, self).visit(node)

  def suffix(self, node, oneline=False):
    """Account for some amount of whitespace as the suffix to a node."""
    self.attr(node, 'suffix', [lambda: self.ws(oneline=oneline)])

  def prefix(self, node):
    """Account for some amount of whitespace as the prefix to a node."""
    self.attr(node, 'prefix', [self.ws])

  def ws(self, oneline=False):
    """Account for some amount of whitespace.

    Arguments:
      oneline: (bool) Whether the whitespace can span more than one line.
    """
    return ''

  @abc.abstractmethod
  def token():
    """Account for a specific token."""

  @abc.abstractmethod
  def optional_suffix(node, attr_name, token_val):
    """Account for a suffix that may or may not occur."""

  @spaced
  def visit_Module(self, node):
    self.generic_visit(node)
    self.attr(node, 'suffix', [self.ws])

  @abc.abstractmethod
  def visit_Str(self, node):
    pass

  @abc.abstractmethod
  def visit_Num(self, node):
    pass

  @parenthesizable
  def visit_Expr(self, node):
    self.visit(node.value)

  @parenthesizable
  def visit_Tuple(self, node):
    for elt in node.elts:
      self.visit(elt)
      self.suffix(elt)
      if elt != node.elts[-1]:
        self.token(',')
    if node.elts:
      self.optional_suffix(node, 'extracomma', ',')

  @parenthesizable
  def visit_Assign(self, node):
    for target in node.targets:
      self.visit(target)
      self.suffix(target)
      self.token('=')
    self.visit(node.value)

  @parenthesizable
  def visit_AugAssign(self, node):
    self.visit(node.target)
    self.suffix(node.target)
    op_token = '%s=' % ast_constants.NODE_TYPE_TO_TOKENS[type(node.op)][0]
    self.token(op_token)
    self.visit(node.value)

  @parenthesizable
  def visit_BinOp(self, node):
    self.visit(node.left)
    self.suffix(node.left)
    self.visit(node.op)
    self.visit(node.right)
    self.suffix(node.right)

  @parenthesizable
  def visit_BoolOp(self, node):
    for value in node.values:
      self.visit(value)
      if value != node.values[-1]:
        self.suffix(value)
        self.visit(node.op)

  @parenthesizable
  def visit_UnaryOp(self, node):
    self.visit(node.op)
    self.visit(node.operand)

  @parenthesizable
  def visit_Lambda(self, node):
    self.token('lambda')
    self.visit(node.args)
    self.token(':')
    self.visit(node.body)

  @spaced
  def visit_Import(self, node):
    self.token('import')
    for alias in node.names:
      self.visit(alias)
      if alias != node.names[-1]:
        self.suffix(alias)
        self.token(',')

  @spaced
  def visit_ImportFrom(self, node):
    self.token('from')
    self.attr(node, 'module_prefix', [self.ws], default=' ')

    module_pattern = ['.', self.ws] * node.level
    if node.module:
      parts = node.module.split('.')
      for part in parts[:-1]:
        module_pattern += [self.ws, part, '.']
      module_pattern += [self.ws, parts[-1]]

    self.attr(node, 'module', module_pattern,
              deps=('level', 'module'),
              default='.' * node.level + (node.module or ''))
    self.attr(node, 'module_suffix', [self.ws], default=' ')

    self.token('import')
    for alias in node.names:
      self.visit(alias)
      if alias != node.names[-1]:
        self.token(',')

  @parenthesizable
  def visit_Compare(self, node):
    self.visit(node.left)
    for op, comparator in zip(node.ops, node.comparators):
      self.visit(op)
      self.visit(comparator)

  def visit_Add(self, node):
    self.token(ast_constants.NODE_TYPE_TO_TOKENS[type(node)][0])

  def visit_Sub(self, node):
    self.token(ast_constants.NODE_TYPE_TO_TOKENS[type(node)][0])

  def visit_Mult(self, node):
    self.token(ast_constants.NODE_TYPE_TO_TOKENS[type(node)][0])

  def visit_Div(self, node):
    self.token(ast_constants.NODE_TYPE_TO_TOKENS[type(node)][0])

  def visit_Mod(self, node):
    self.token(ast_constants.NODE_TYPE_TO_TOKENS[type(node)][0])

  def visit_Pow(self, node):
    self.token(ast_constants.NODE_TYPE_TO_TOKENS[type(node)][0])

  def visit_LShift(self, node):
    self.token(ast_constants.NODE_TYPE_TO_TOKENS[type(node)][0])

  def visit_RShift(self, node):
    self.token(ast_constants.NODE_TYPE_TO_TOKENS[type(node)][0])

  def visit_BitAnd(self, node):
    self.token(ast_constants.NODE_TYPE_TO_TOKENS[type(node)][0])

  def visit_BitOr(self, node):
    self.token(ast_constants.NODE_TYPE_TO_TOKENS[type(node)][0])

  def visit_BitXor(self, node):
    self.token(ast_constants.NODE_TYPE_TO_TOKENS[type(node)][0])

  def visit_FloorDiv(self, node):
    self.token(ast_constants.NODE_TYPE_TO_TOKENS[type(node)][0])

  def visit_Invert(self, node):
    self.token(ast_constants.NODE_TYPE_TO_TOKENS[type(node)][0])

  def visit_Not(self, node):
    self.token(ast_constants.NODE_TYPE_TO_TOKENS[type(node)][0])

  def visit_UAdd(self, node):
    self.token(ast_constants.NODE_TYPE_TO_TOKENS[type(node)][0])

  def visit_USub(self, node):
    self.token(ast_constants.NODE_TYPE_TO_TOKENS[type(node)][0])

  def visit_And(self, node):
    self.token(ast_constants.NODE_TYPE_TO_TOKENS[type(node)][0])

  def visit_Or(self, node):
    self.token(ast_constants.NODE_TYPE_TO_TOKENS[type(node)][0])

  @spaced
  def visit_Eq(self, node):
    self.token(ast_constants.NODE_TYPE_TO_TOKENS[type(node)][0])

  @spaced
  def visit_NotEq(self, node):
    self.token(ast_constants.NODE_TYPE_TO_TOKENS[type(node)][0])

  @spaced
  def visit_Lt(self, node):
    self.token(ast_constants.NODE_TYPE_TO_TOKENS[type(node)][0])

  @spaced
  def visit_LtE(self, node):
    self.token(ast_constants.NODE_TYPE_TO_TOKENS[type(node)][0])

  @spaced
  def visit_Gt(self, node):
    self.token(ast_constants.NODE_TYPE_TO_TOKENS[type(node)][0])

  @spaced
  def visit_GtE(self, node):
    self.token(ast_constants.NODE_TYPE_TO_TOKENS[type(node)][0])

  @spaced
  def visit_Is(self, node):
    self.token(ast_constants.NODE_TYPE_TO_TOKENS[type(node)][0])

  @spaced
  def visit_IsNot(self, node):
    self.attr(node, 'content', ['is', self.ws, 'not'], default='is not')

  @spaced
  def visit_In(self, node):
    self.token(ast_constants.NODE_TYPE_TO_TOKENS[type(node)][0])

  @spaced
  def visit_NotIn(self, node):
    self.attr(node, 'content', ['not', self.ws, 'in'], default='not in')

  @spaced
  def visit_alias(self, node):
    self.token(node.name)
    if node.asname is not None:
      self.attr(node, 'asname', [self.ws, 'as', self.ws], default=' as ')
      self.token(node.asname)

  @spaced
  def visit_If(self, node):
    self.token('elif' if ast_utils.prop(node, 'is_elif') else 'if')
    self.visit(node.test)
    self.attr(node, 'testsuffix', [self.ws, ':', self.ws], default=':')
    for stmt in node.body:
      self.visit(stmt)

    if node.orelse:
      if (len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If) and
          self.check_is_elif(node.orelse[0])):
        ast_utils.setprop(node.orelse[0], 'is_elif', True)
        self.visit(node.orelse[0])
      else:
        self.attr(node, 'elseprefix', [self.ws])
        self.token('else')
        self.attr(node, 'elsesuffix', [self.ws, ':', self.ws], default=':')
        for stmt in node.orelse:
          self.visit(stmt)

  @abc.abstractmethod
  def check_is_elif(self):
    """Return True if the node continues a previous `if` statement as `elif`.

    In python 2.x, `elif` statments get parsed as If nodes. E.g, the following
    two syntax forms are indistinguishable in the ast in python 2.

    if a:
      do_something()
    elif b:
      do_something_else()

    if a:
      do_something()
    else:
      if b:
        do_something_else()

    This method should return True for the 'if b' node if it has the first form.
    """

  @parenthesizable
  def visit_IfExp(self, node):
    self.visit(node.body)
    self.suffix(node.body)
    self.token('if')
    self.visit(node.test)
    self.suffix(node.test)
    self.token('else')
    self.visit(node.orelse)

  @spaced
  def visit_While(self, node):
    self.token('while')
    self.visit(node.test)
    self.attr(node, 'testsuffix', [self.ws, ':', self.ws], default=':')
    for stmt in node.body:
      self.visit(stmt)

    if node.orelse:
      self.attr(node, 'elseprefix', [self.ws])
      self.token('else')
      self.attr(node, 'elsesuffix', [self.ws, ':', self.ws], default=':')
      for stmt in node.orelse:
        self.visit(stmt)

  @spaced
  def visit_For(self, node):
    self.token('for')
    self.visit(node.target)
    self.suffix(node.target)
    self.token('in')
    self.visit(node.iter)
    self.suffix(node.iter)
    self.token(':')
    for stmt in node.body:
      self.visit(stmt)

    if node.orelse:
      self.attr(node, 'orelseprefix', [self.ws])
      self.token('else')
      self.token(':')

      for stmt in node.orelse:
        self.visit(stmt)

  @spaced
  def visit_Repr(self, node):
    raise NotImplementedError()

  @spaced
  def visit_With(self, node):
    if hasattr(node, 'items'):
      return self.visit_With_3(node)
    if not getattr(node, 'is_continued', False):
      self.token('with')
    self.visit(node.context_expr)
    self.suffix(node.context_expr)
    if node.optional_vars:
      self.token('as')
      self.visit(node.optional_vars)
      self.suffix(node.optional_vars)

    if self.check_is_continued_with(node.body[0]):
      node.body[0].is_continued = True
      self.token(',')
    else:
      self.token(':')

    for stmt in node.body:
      self.visit(stmt)

  @abc.abstractmethod
  def check_is_continued_with(self, node):
    """Return True if the node continues a previous `with` statement.

    In python 2.x, `with` statments with many context expressions get parsed as
    a tree of With nodes. E.g, the following two syntax forms are
    indistinguishable in the ast in python 2.

    with a, b, c:
      do_something()

    with a:
      with b:
        with c:
          do_something()

    This method should return True for the `with b` and `with c` nodes.
    """

  @spaced
  def visit_With_3(self, node):
    self.token('with')

    for i, withitem in enumerate(node.items):
      self.visit(withitem)
      if i != len(node.items) - 1:
        self.token(',')

    self.token(':')
    for stmt in node.body:
      self.visit(stmt)

  @spaced
  def visit_withitem(self, node):
    self.visit(node.context_expr)
    self.suffix(node.context_expr)
    if node.optional_vars:
      self.token('as')
      self.visit(node.optional_vars)
      self.suffix(node.optional_vars)

  @spaced
  def visit_Assert(self, node):
    self.token('assert')
    self.visit(node.test)
    if node.msg:
      self.token(',')
      self.visit(node.msg)

  @spaced
  def visit_Exec(self, node):
    raise NotImplementedError()

  @spaced
  def visit_Global(self, node):
    self.token('global')

  @parenthesizable
  def visit_Name(self, node):
    self.token(node.id)

  @parenthesizable
  def visit_NameConstant(self, node):
    self.token(str(node.value))

  @parenthesizable
  def visit_Attribute(self, node):
    self.visit(node.value)
    self.attr(node, 'dot', [self.ws, '.', self.ws], default='.')
    self.token(node.attr)

  @parenthesizable
  def visit_Subscript(self, node):
    self.visit(node.value)
    self.visit(node.slice)

  @spaced
  def visit_Index(self, node):
    self.token('[')
    self.visit(node.value)
    self.suffix(node.value)
    self.token(']')

  @spaced
  def visit_Slice(self, node):
    self.token('[')

    if node.lower:
      self.visit(node.lower)
      self.suffix(node.lower)
    else:
      self.attr(node, 'lowerspace', [self.ws])

    if node.lower or node.upper:
      self.token(':')

    if node.upper:
      self.visit(node.upper)
      self.suffix(node.upper)
    else:
      self.attr(node, 'upperspace', [self.ws])

    if node.step:
      self.token(':')
      self.visit(node.step)
      self.suffix(node.step)
    else:
      self.attr(node, 'stepspace', [self.ws])

    self.token(']')

  @parenthesizable
  def visit_List(self, node):
    self.token('[')

    for elt in node.elts:
      self.visit(elt)
      self.suffix(elt)
      if elt != node.elts[-1]:
        self.token(',')
    if node.elts:
      self.optional_suffix(node, 'extracomma', ',')

    self.attr(node, 'close_prefix', [self.ws])
    self.token(']')

  @parenthesizable
  def visit_Set(self, node):
    self.token('{')

    for elt in node.elts:
      self.visit(elt)
      self.suffix(elt)
      if elt != node.elts[-1]:
        self.token(',')
    if node.elts:
      self.optional_suffix(node, 'extracomma', ',')

    self.token('}')

  @parenthesizable
  def visit_Dict(self, node):
    self.token('{')

    for key, value in zip(node.keys, node.values):
      self.visit(key)
      self.suffix(key)
      self.token(':')
      self.visit(value)
      if value != node.values[-1]:
        self.suffix(value)
        self.token(',')
    self.optional_suffix(node, 'extracomma', ',')
    self.attr(node, 'close_prefix', [self.ws])
    self.token('}')

  @parenthesizable
  def visit_GeneratorExp(self, node):
    self.visit(node.elt)
    self.suffix(node.elt)
    for comp in node.generators:
      self.token('for')
      self.visit(comp)

  @parenthesizable
  def visit_ListComp(self, node):
    self._comp_exp(node, open_brace='[', close_brace=']')

  @parenthesizable
  def visit_SetComp(self, node):
    self._comp_exp(node, open_brace='{', close_brace='}')

  def _comp_exp(self, node, open_brace=None, close_brace=None):
    if open_brace:
      self.token(open_brace)
    self.visit(node.elt)
    self.suffix(node.elt)
    for comp in node.generators:
      self.token('for')
      self.visit(comp)
    if close_brace:
      self.token(close_brace)

  @parenthesizable
  def visit_DictComp(self, node):
    self.token('{')
    self.visit(node.key)
    self.suffix(node.key)
    self.token(':')
    self.visit(node.value)
    self.suffix(node.value)
    for comp in node.generators:
      self.token('for')
      self.visit(comp)
    self.token('}')

  @spaced
  def visit_comprehension(self, node):
    self.visit(node.target)
    self.suffix(node.target)
    self.token('in')
    self.visit(node.iter)
    self.suffix(node.iter)
    for if_expr in node.ifs:
      self.token('if')
      self.visit(if_expr)
      if if_expr != node.ifs[-1]:
        self.suffix(if_expr)

  @parenthesizable
  def visit_Call(self, node):
    self.visit(node.func)
    self.suffix(node.func)
    self.token('(')
    num_items = (len(node.args) + len(node.keywords) +
                 (1 if node.starargs else 0) + (1 if node.kwargs else 0))

    i = 0
    for arg in node.args:
      self.visit(arg)
      self.suffix(arg)
      if i < num_items - 1:
        self.token(',')
      i += 1

    starargs_idx = ast_utils.find_starargs(node)
    kw_end = len(node.args) + len(node.keywords) + (1 if node.starargs else 0)
    kw_idx = 0
    while i < kw_end:
      if i == starargs_idx:
        self.attr(node, 'starargs_prefix', [self.ws, '*'], default='*')
        self.visit(node.starargs)
        self.suffix(node.starargs)
      else:
        self.visit(node.keywords[kw_idx])
        self.suffix(node.keywords[kw_idx])
        kw_idx += 1
      if i < num_items - 1:
        self.token(',')
      i += 1

    if node.kwargs:
      self.attr(node, 'kwargs_prefix', [self.ws, '**'], default='**')
      self.visit(node.kwargs)
      self.suffix(node.kwargs)

    if num_items > 0:
      self.optional_suffix(node, 'extracomma', ',')

    self.token(')')

  @spaced
  def visit_arguments(self, node):
    total_args = (len(node.args) +
                  (1 if node.vararg else 0) +
                  (1 if node.kwarg else 0))
    arg_i = 0

    positional = node.args[:-len(node.defaults)] if node.defaults else node.args
    keyword = node.args[-len(node.defaults):] if node.defaults else node.args

    for arg in positional:
      self.visit(arg)
      self.suffix(arg)
      arg_i += 1
      if arg_i < total_args:
        self.token(',')

    for arg, default in zip(keyword, node.defaults):
      self.visit(arg)
      self.suffix(arg)
      self.token('=')
      self.visit(default)
      self.suffix(default)
      arg_i += 1
      if arg_i < total_args:
        self.token(',')

    if node.vararg:
      self.attr(node, 'vararg_prefix', [self.ws, '*', self.ws], default='*')
      if isinstance(node.vararg, ast.AST):
        self.visit(node.vararg)
      else:
        self.token(node.vararg)
        self.attr(node, 'vararg_suffix', [self.ws])
      arg_i += 1
      if arg_i < total_args:
        self.token(',')

    if node.kwarg:
      self.attr(node, 'kwarg_prefix', [self.ws, '**', self.ws], default='**')
      if isinstance(node.kwarg, ast.AST):
        self.visit(node.kwarg)
      else:
        self.token(node.kwarg)
        self.attr(node, 'kwarg_suffix', [self.ws])

  @spaced
  def visit_arg(self, node):
    self.token(node.arg)
    self.suffix(node)
    if node.annotation is not None:
      self.token(':')
      self.visit(node.annotation)

  @spaced
  def visit_FunctionDef(self, node):
    for decorator in node.decorator_list:
      self.token('@')
      self.visit(decorator)
      self.suffix(decorator)
    self.token('def')
    self.attr(node, 'name_prefix', [self.ws])
    self.token(node.name)
    self.attr(node, 'name_suffix', [self.ws])
    self.token('(')
    self.visit(node.args)
    self.token(')')

    if getattr(node, 'returns', None):
      self.attr(node, 'returns_prefix', [self.ws, '->', self.ws],
                deps=('returns',), default=' -> ')
      self.visit(node.returns)

    self.token(':')

    for expr in node.body:
      self.visit(expr)

  @spaced
  def visit_keyword(self, node):
    self.token(node.arg)
    self.attr(node, 'eq', [self.ws, '='], default='=')
    self.visit(node.value)

  @spaced
  def visit_Return(self, node):
    self.token('return')
    if node.value:
      self.visit(node.value)

  @spaced
  def visit_Yield(self, node):
    self.token('yield')
    if node.value:
      self.visit(node.value)

  @spaced
  def visit_Delete(self, node):
    self.token('del')
    for target in node.targets:
      self.visit(target)
      self.suffix(target)
      if target != node.targets[-1]:
        self.token(',')

  @spaced
  def visit_Print(self, node):
    self.token('print')
    self.attr(node, 'print_suffix', [self.ws], default=' ')
    if node.dest:
      self.token('>>')
      self.visit(node.dest)
      if node.values or not node.nl:
        self.suffix(node.dest)
        self.token(',')

    for value in node.values:
      self.visit(value)
      if value != node.values[-1] or not node.nl:
        self.suffix(value)
        self.token(',')

  @spaced
  def visit_ClassDef(self, node):
    for decorator in node.decorator_list:
      self.token('@')
      self.visit(decorator)
      self.suffix(decorator)
    self.token('class')
    self.attr(node, 'name_prefix', [self.ws], default=' ')
    self.token(node.name)
    self.attr(node, 'name_suffix', [self.ws])
    self.token('(')
    for base in node.bases:
      self.visit(base)
      self.suffix(base)
      if base != node.bases[-1]:
        self.token(',')
    self.token(')')
    self.token(':')

    for expr in node.body:
      self.visit(expr)

  @spaced
  def visit_Pass(self, node):
    self.token('pass')

  @spaced
  def visit_Break(self, node):
    self.token('break')

  @spaced
  def visit_Continue(self, node):
    self.token('continue')

  @spaced
  def visit_TryFinally(self, node):
    # Try with except and finally is a TryFinally with the first statement as a
    # TryExcept in Python2
    if not isinstance(node.body[0], ast.TryExcept):
      self.attr(node, 'open_try', ['try', self.ws, ':'], default='try:')
    for stmt in node.body:
      self.visit(stmt)
    self.attr(node, 'open_finally', ['finally', self.ws, ':'],
              default='finally:')
    for stmt in node.finalbody:
      self.visit(stmt)

  @spaced
  def visit_TryExcept(self, node):
    self.attr(node, 'open_try', ['try', self.ws, ':'], default='try:')
    for stmt in node.body:
      self.visit(stmt)
    for handler in node.handlers:
      self.visit(handler)
    if node.orelse:
      self.attr(node, 'open_else', ['else', self.ws, ':'], default='else:')
      for stmt in node.orelse:
        self.visit(stmt)

  @spaced
  def visit_Try(self, node):
    # Python 3
    self.attr(node, 'open_try', ['try', self.ws, ':'], default='try:')
    for stmt in node.body:
      self.visit(stmt)
    for handler in node.handlers:
      self.visit(handler)
    if node.orelse:
      self.attr(node, 'open_else', ['else', self.ws, ':'], default='else:')
      for stmt in node.orelse:
        self.visit(stmt)
    if node.finalbody:
      self.attr(node, 'open_finally', ['finally', self.ws, ':'],
                default='finally:')
      for stmt in node.finalbody:
        self.visit(stmt)

  @spaced
  def visit_ExceptHandler(self, node):
    self.token('except')
    if node.type:
      self.visit(node.type)
      self.suffix(node.type)
    if node.type and node.name:
      self.attr(node, 'as', [self.ws, 'as', self.ws], default=' as ')
    if node.name:
      if isinstance(node.name, ast.AST):
        self.visit(node.name)
      else:
        self.token(node.name)
        self.attr(node, 'name_suffix', [self.ws])
    self.token(':')
    for stmt in node.body:
      self.visit(stmt)

  @spaced
  def visit_Raise(self, node):
    self.token('raise')
    if node.type:
      self.visit(node.type)
    if node.inst:
      self.suffix(node.type)
      self.token(',')
      self.visit(node.inst)
    if node.tback:
      self.suffix(node.inst)
      self.token(',')
      self.visit(node.tback)

  @contextlib.contextmanager
  def scope(self, node):
    """Context manager to handle a parenthesized scope."""
    yield


class AstAnnotator(BaseVisitor):

  def __init__(self, source):
    self.tokens = token_generator.TokenGenerator(source)

  @parenthesizable
  def visit_Num(self, node):
    """Annotate a Num node with the exact number format."""
    token_number_type = token_generator.TOKENS.NUMBER
    contentargs = [lambda: self.tokens.next_of_type(token_number_type)[1]]
    if node.n < 0:
      contentargs.insert(0, '-')
    self.attr(node, 'content', contentargs, deps=('n',), default=str(node.n))

  @parenthesizable
  def visit_Str(self, node):
    """Annotate a Str node with the exact string format."""
    self.attr(node, 'content', [self.tokens.str], deps=('s',), default=node.s)

  def check_is_elif(self, node):
    """Return True iff the If node is an `elif` in the source."""
    next_tok = self.tokens.next_name()
    return isinstance(node, ast.If) and next_tok[1] == 'elif'

  def check_is_continued_with(self, node):
    """Return True iff the With node is a continued `with` in the source."""
    return isinstance(node, ast.With) and self.tokens.peek()[1] == ','

  def ws(self, oneline=False):
    """Parse some whitespace from the source tokens and return it."""
    return self.tokens.whitespace(oneline=oneline)

  def token(self, token_val):
    """Parse a single token with exactly the given value."""
    token = self.tokens.next()
    if token[1] != token_val:
      raise ValueError("Expected %r but found %r\nline %d: %s" % (
          token_val, token[1], token[2][0], self.tokens._lines[token[2][0] - 1]))

    # If the token opens or closes a parentheses scope, keep track of it
    if token[1] in '({[':
      self.tokens.hint_open()
    elif token[1] in ')}]':
      self.tokens.hint_closed()

    return token[1]

  def optional_suffix(self, node, attr_name, token_val):
    """Try to parse a suffix and attach it to the node."""
    token = self.tokens.peek()
    if token and token[1] == token_val:
      self.tokens.next()
      ast_utils.appendprop(node, attr_name, token[1] + self.ws())

  def attr(self, node, attr_name, attr_vals, deps=None, default=None):
    """Parses some source and sets an attribute on the given node.

    Stores some arbitrary formatting information on the node. This takes a list
    attr_vals which tell what parts of the source to parse. The result of each
    function is concatenated onto the formatting data, and strings in this list
    are a shorthand to look for an exactly matching token.

    For example:
      self.attr(node, 'foo', ['(', self.ws, 'Hello, world!', self.ws, ')'],
                deps=('s',), default=node.s)

    is a rudimentary way to parse a parenthesized string. After running this,
    the matching source code for this node will be stored in its formatting
    dict under the key 'foo'. The result might be `(\n  'Hello, world!'\n)`.

    This also keeps track of the current value of each of the dependencies.
    In the above example, we would have looked for the string 'Hello, world!'
    because that's the value of node.s, however, when we print this back, we
    want to know if the value of node.s has changed since this time. If any of
    the dependent values has changed, the default would be used instead.

    Arguments:
      node: (ast.AST) An AST node to attach formatting information to.
      attr_name: (string) Name to store the formatting information under.
      attr_vals: (list of functions/strings) Each item is either a function
        that parses some source and return a string OR a string to match
        exactly (as a token).
      deps: (optional, set of strings) Attributes of the node which attr_vals
        depends on.
      default: (string) Unused here.
    """
    del default  # unused
    if deps:
      for dep in deps:
        ast_utils.setprop(node, dep + '__src', getattr(node, dep, None))
    for attr_val in attr_vals:
      if isinstance(attr_val, six.string_types):
        ast_utils.appendprop(node, attr_name, self.token(attr_val))
      else:
        ast_utils.appendprop(node, attr_name, attr_val())

  def scope(self, node):
    """Return a context manager to handle a parenthesized scope."""
    return self.tokens.scope(node)

  def _optional_suffix(self, token_type, token_val):
    token = self.tokens.peek()
    if token[0] != token_type or token[1] != token_val:
      return ''
    else:
      self.tokens.next()
      return token[1] + self.ws()
