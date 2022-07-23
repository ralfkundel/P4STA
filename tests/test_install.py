import unittest
import os
from stat import *
import sys


class TestP4staInstall(unittest.TestCase):
    def test_chmod(self):
        root = os.path.dirname(os.path.realpath(__file__)).split("tests")[0]
        files = ["run.sh", "install.sh", "cli.sh", "gui.sh", "run_test.sh"]
        for file in files:
            if file.endswith(".sh") and file != "create_GitHub.sh":
                path = os.path.join(root, file)
                as_oct = oct(os.stat(path)[ST_MODE])
                print(as_oct)
                rights = int(as_oct[-3:])
                print(str(rights) + " :" + path)
                self.assertTrue(((rights >= 775) | (rights == 755)))


unittest.main(exit=True)
