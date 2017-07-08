"""
Copyright 2016  Korea University & EMCS Labs  (Author: Hyungwon Yang)
Apache 2.0

*** Introduction ***
This script adjust floating precision in final_ali.txt

*** USAGE ***
Ex. python generate_textgrid.py $data_file $adjusted_file

"""

import sys

if len(sys.argv) != 3:
    print("Input arguments are incorrectly provided. Four argument should be assigned.")
    print("1. Data file.")
    print("2. Save file.")
    print("*** USAGE ***")
    print("Ex. python generate_textgrid.py $data_file $save_file")
    raise ValueError('RETURN')


data_file = sys.argv[1]
save_file = sys.argv[2]

# Import data file.
with open(data_file,'r') as data:
    ali = data.readlines()

# Adjust floating points.
with open(save_file,'w') as save:
    for line in ali:
        tmp_line = line.split('\t')
        start = round(float(line.split('\t')[-2]),2)
        end = round(float(line.split('\t')[-1]),2)
        tmp_line[-2] = str(start)
        tmp_line[-1] = str(end)
        new_line = '\t'.join(tmp_line)
        save.write(new_line+'\n')

