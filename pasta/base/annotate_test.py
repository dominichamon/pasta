# coding=utf-8
"""Tests for annotate."""
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
import difflib
import os.path
import unittest

import pasta
from pasta.base import annotate
from pasta.base import ast_utils
from pasta.base import codegen
from pasta.base import test_utils

TESTDATA_DIR = os.path.realpath(
    os.path.join(os.path.dirname(pasta.__file__), '../testdata'))


class SymmetricTest(test_utils.TestCase):
  pass


def symmetric_test_generator(filepath):
  def test(self):
    with open(filepath, 'r') as handle:
      src = handle.read()

    t = ast_utils.parse(src)
    annotator = annotate.AstAnnotator(src)
    annotator.visit(t)

    output = codegen.to_str(t)

    self.assertEqual([], annotator.tokens._parens, 'Unmatched parens')
    self.assertMultiLineEqual(output, src)
  return test


def get_diff(before, after):
  return difflib.ndiff(after.splitlines(), before.splitlines())


def _is_syntax_valid(filepath):
  with open(filepath, 'r') as f:
    try:
      ast.parse(f.read())
    except SyntaxError:
      return False
  return True


data_dir = os.path.join(TESTDATA_DIR, 'ast')
for dirpath, dirs, files in os.walk(data_dir):
  for filename in files:
    if filename.endswith('.in'):
      full_path = os.path.join(dirpath, filename)
      setattr(SymmetricTest, 'test_symmetric_' + filename[:-3], unittest.skipIf(
                not _is_syntax_valid(full_path),
                'Test contains syntax not supported by this version.',
              )(symmetric_test_generator(full_path)))


def suite():
  result = unittest.TestSuite()
  result.addTests(unittest.makeSuite(SymmetricTest))
  return result


if __name__ == '__main__':
  unittest.main()
