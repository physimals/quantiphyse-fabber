import sys
import time
import unittest

from quantiphyse.test.widget_test import WidgetTest

from .widget import FabberModellingWidget

class FabberWidgetTest(WidgetTest):

    def widget_class(self):
        return FabberModellingWidget

    def test_no_data(self):
        """ User clicks the run button with no data"""
        if self.w.run_box.runBtn.isEnabled():
            self.w.run_box.runBtn.clicked.emit()
        self.assertFalse(self.error)

    @unittest.skipIf("--fast" in sys.argv, "Slow test")
    def test_just_click_run(self):
        """ User loads some data and clicks the run button """
        self.ivm.add(self.data_4d, grid=self.grid, name="data_4d")
        self.ivm.add(self.mask, grid=self.grid, name="mask")
        self.w.run_box.runBtn.clicked.emit()
        while not hasattr(self.w.run_box, "log"):
            self.processEvents()
            time.sleep(2)
        self.assertTrue("mean_c0" in self.ivm.data)
        self.assertTrue("mean_c1" in self.ivm.data)
        self.assertTrue("mean_c2" in self.ivm.data)
        self.assertTrue("modelfit" in self.ivm.data)
        self.assertFalse(self.error)

if __name__ == '__main__':
    unittest.main()
