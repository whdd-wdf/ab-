import argparse
import csv
import json
import os
import subprocess
import sys
import datetime

GATE_OPEN_MIN = 7 * 60 + 30
GATE_CLOSE_MIN = 17 * 60 + 5
TICK = {"510300": 0.001, "513650": 0.001}
A_CODES = {"510300": "A1", "601088": "A2", "513650": "A3"}
MARK_OF_LINE = {"A1": "", "A2": "", "A3": "", "B": ""}
NAMES = {"510300": "300ETF", "601088": "中国神华", "513650": "标普ETF", "600919": "江苏银行", "600176": "中国巨石", "002475": "立讯精密", "000596": "古井贡酒", "600018": "上港集团", "603198": "迎驾贡酒", "000001": "平安银行", "600000": "浦发银行"}
tick_of = lambda code: TICK.get(code, 0.01)