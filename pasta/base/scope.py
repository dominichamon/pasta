# coding=utf-8
"""Perform static analysis on python syntax trees."""
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

import ast

# TODO: Support relative imports


class ScopeVisitor(ast.NodeVisitor):

  def __init__(self):
    super(ScopeVisitor, self).__init__()
    self.root_scope = self.scope = RootScope()
    self._parent = None

  def visit(self, node):
    if node is None:
      return
    self.root_scope.set_parent(node, self._parent)
    tmp = self._parent
    self._parent = node
    super(ScopeVisitor, self).visit(node)
    self._parent = tmp

  def visit_in_order(self, node, *attrs):
    for attr in attrs:
      try:
        val = getattr(node, attr)
        if isinstance(val, list):
          for item in val:
            self.visit(item)
        else:
          self.visit(val)
      except AttributeError:
        pass

  def visit_Import(self, node):
    for alias in node.names:
      name_parts = alias.name.split('.')

      # Always reference imported names
      self.scope.add_external_reference(alias.name, alias)

      if not alias.asname:
        # If not aliased, define the top-level module of the import
        cur_name = self.scope.define_name(name_parts[0], alias)

        # Define names of sub-modules imported
        for part in name_parts[1:]:
          cur_name = cur_name.lookup_name(part)
          cur_name.define(alias)

      else:
        # If the imported name is aliased, define that name only
        self.scope.define_name(alias.asname, alias)
    self.generic_visit(node)

  def visit_ImportFrom(self, node):
    if node.module:
      self.scope.add_external_reference(node.module, node)
    for alias in node.names:
      self.scope.define_name(alias.asname or alias.name, alias)
      if node.module:
        self.scope.add_external_reference(node.module + '.' + alias.name, alias,
                                          packages=False)
      # TODO: else? relative imports
    self.generic_visit(node)

  def visit_Name(self, node):
    if isinstance(node.ctx, (ast.Store, ast.Param)):
      self.scope.define_name(node.id, node)
    elif isinstance(node.ctx, ast.Load):
      self.scope.lookup_name(node.id).add_reference(node)
      self.root_scope.set_name_for_node(node, self.scope.lookup_name(node.id))
    self.generic_visit(node)

  def visit_FunctionDef(self, node):
    try:
      self.scope.define_name(node.name, node)
      self.scope = Scope(self.scope)
      # Visit decorator list first to avoid declarations in args
      self.visit_in_order(node, 'decorator_list', 'args', 'returns', 'body')
    finally:
      self.scope = self.scope.parent_scope

  def visit_arguments(self, node):
    # Visit defaults first to avoid declarations in args
    self.visit_in_order(node, 'defaults', 'args', 'vararg', 'kwarg')

  def visit_arg(self, node):
    self.scope.define_name(node.arg, node)
    self.generic_visit(node)

  def visit_ClassDef(self, node):
    try:
      self.scope.define_name(node.name, node)
      self.scope = Scope(self.scope)
      self.generic_visit(node)
    finally:
      self.scope = self.scope.parent_scope

  def visit_Attribute(self, node):
    self.generic_visit(node)
    node_value_name = self.root_scope.get_name_for_node(node.value)
    if node_value_name:
      node_name = node_value_name.lookup_name(node.attr)
      self.root_scope.set_name_for_node(node, node_name)
      node_name.add_reference(node)


class Scope(object):

  def __init__(self, parent_scope):
    self.parent_scope = parent_scope
    self.names = {}

  def add_external_reference(self, name, node, packages=True):
    self.parent_scope.add_external_reference(name, node, packages=packages)

  def define_name(self, name, node):
    try:
      name_obj = self.names[name]
    except KeyError:
      name_obj = self.names[name] = Name(name)
    name_obj.define(node)
    return name_obj

  def lookup_name(self, name):
    try:
      return self.names[name]
    except KeyError:
      pass
    if self.parent_scope is None:
      name_obj = self.names[name] = Name(name)
      return name_obj
    return self.parent_scope.lookup_name(name)

  def get_root_scope(self):
    return self.parent_scope.get_root_scope()


class RootScope(Scope):

  def __init__(self):
    super(RootScope, self).__init__(None)
    self.external_references = {}
    self._parents = {}
    self._nodes_to_names = {}

  def add_external_reference(self, name, node, packages=True):
    names_to_add = [name]
    if packages:
      parts = name.split('.')
      names_to_add.extend('.'.join(parts[:i]) for i in range(1, len(parts)))

    for n in names_to_add:
      if n in self.external_references:
        self.external_references[n].append(node)
      else:
        self.external_references[n] = [node]

  def get_root_scope(self):
    return self

  def parent(self, node):
    return self._parents[node]

  def set_parent(self, node, parent):
    self._parents[node] = parent

  def get_name_for_node(self, node):
    return self._nodes_to_names.get(node, None)

  def set_name_for_node(self, node, name):
    self._nodes_to_names[node] = name


# Should probably also have a scope?
class Name(object):

  def __init__(self, id):
    self.id = id
    self.definition = None
    self.reads = []
    self.attrs = {}

  def add_reference(self, node):
    self.reads.append(node)

  def define(self, node):
    if self.definition:
      self.reads.append(node)
    else:
      self.definition = node

  def lookup_name(self, name):
    try:
      return self.attrs[name]
    except KeyError:
      name_obj = self.attrs[name] = Name(name)
      return name_obj


def analyze(tree):
  v = ScopeVisitor()
  v.visit(tree)
  return v.scope
