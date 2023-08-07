#!?bin/bash
# This script generate g2p lexicon file. 
# 
# 20.03.26
# Hyungwon Yang
# NAMZ labs

if [ $# -ne 2 ]; then
   echo "USAGE: [input: mecab text file] [output: lexicon file]"
   echo "1. input: mecab sentence text file."
   echo "2. otuput: lexicon file." && exit 1
fi

# input arguments
input_text=$1
save_file=$2

# make work directory.
work_dir=`mktemp -d`
if [ -d $work_dir ]; then
    rm -rf $work_dir
fi
mkdir $work_dir

echo "sorting files"
cat $input_text | tr ' ' '\n' | grep -v "+ー" | grep -v "++" | grep -v "×" > $work_dir/word.txt
cat $work_dir/word.txt | sort -u > $work_dir/sorted_word.txt
echo "activating g2p process"
src/local/vocab2dic.pl -p src/local/kana2phone -e $work_dir/error.txt -o $work_dir/word.txt $work_dir/sorted_word.txt
echo "finalizing"
cut -d'+' -f1,3- $work_dir/word.txt > $work_dir/sorted_word.txt
cut -f1,3- $work_dir/sorted_word.txt | perl -ape 's:\t: :g' > $save_file

rm -rf $work_dir

echo "DONE"
