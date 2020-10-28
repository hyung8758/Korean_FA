#!/bin/bash
# Copyright 2016  Korea University & EMCS Labs  (Author: Hyungwon Yang)
# Apache 2.0
#
# This script duplicates a givien text file that transcribed wav file 
# along with the names of all wave files. 
# Let's say you have 100 wave files recorded "I want to go to school".
# All the wave files are written in their distinctive labels such as test01.wav, test02.wav and so on.
# And you have one text file that transrbied "I want to go to school", then you can use this script
# for generating all the transcribed text files that corresponds to the name of each wave file.

# get variables.
kaldi=$1
jidx=$2
origin_dir=$3
wav_file=$4
txt_file=$5
tg_word_opt=$6
tg_phone_opp=$7
source_dir=`dirname $wav_file`
work_dir=`dirname $source_dir`

# Model directory
fa_model=model/model4fa
# Code directory
code_dir=src/local/core
# log directory
log_dir=$work_dir/log_$jidx
# source directory
data_dir=$work_dir/data_$jidx
# wuts saved directory
trans_dir=$work_dir/trans_$jidx
# lexicon directory
dict_dir=$work_dir/dict_$jidx
# language directory
lang_dir=$work_dir/lang_$jidx
# result direcotry
result_dir=$work_dir/result_$jidx
# align data directory
ali_dir=$work_dir/fa_dir_$jidx
# raw sentence save directory
raw_sent_dir=$work_dir/raw_sent_$jidx
# Set prono directories.
prono_dir=$work_dir/prono_$jidx

align_nj=1
mfcc_nj=1
passing=0
align_error=0

mkdir -p $log_dir
mkdir -p $data_dir
mkdir -p $trans_dir
mkdir -p $dict_dir
mkdir -p $lang_dir
mkdir -p $result_dir
mkdir -p $ali_dir
mkdir -p $raw_sent_dir
mkdir -p $prono_dir

# mian FA job.
mv $wav_file $txt_file $data_dir
wav_name=`basename $wav_file`
txt_name=`basename $txt_file`
log_name=`echo $wav_name | sed -e "s/.wav//g"`

echo "Audio: $wav_name, Text: $txt_name." > $log_dir/process.$log_name.log

python src/local/fa_prep_data.py $data_dir $trans_dir >> $log_dir/process.$log_name.log || exit 1
$code_dir/utt2spk_to_spk2utt.pl $trans_dir/utt2spk > $trans_dir/spk2utt 
echo "text, textraw, segments, wav.scp, utt2spk, and spk2utt files were generated." >> $log_dir/process.$log_name.log

# Generate raw sentence text file.
words=`cat $data_dir/$txt_name`
txt_rename=`echo $txt_name | sed -e "s/txt/raw/g"`
echo "$words" | tr ' ' '\n' > $raw_sent_dir/$txt_rename
echo "raw_sentence: " >> $log_dir/process.$log_name.log
cat $raw_sent_dir/$txt_rename >> $log_dir/process.$log_name.log

## For Generating new_lexicon file.
# g2p conversion.
echo "Initiating g2p process." >> $log_dir/process.$log_name.log
for div in $words; do
	python src/local/g2p.py $div >> $prono_dir/prono_list
done
paste -d ' ' $raw_sent_dir/$txt_rename $prono_dir/prono_list >> $prono_dir/tmp_lexicon.txt
cat $prono_dir/tmp_lexicon.txt | sort -u > $dict_dir/lexicon.txt
echo "Lexicon: " >> $log_dir/process.$log_name.log
cat $dict_dir/lexicon.txt >> $log_dir/process.$log_name.log

## Language modeling.
# make L.fst
paste -d '\n' $prono_dir/tmp_lexicon.txt model/lexicon.txt | sort | uniq | sed '/^\s*$/d' > $dict_dir/lexicon.txt
bash src/local/prepare_new_lang.sh $dict_dir $lang_dir "<UNK>" &>/dev/null

## Feature extraction.
# MFCC default setting.
echo "Extracting the MFCC features." >> $log_dir/process.$log_name.log
mfccdir=mfcc
cmd="$code_dir/run.pl"

# Wav file sanitiy check.
# Audio file should have only 1 channel.
wav_ch=`sox --i $data_dir/$wav_name | grep "Channels" | awk '{print $3}'`
if [ $wav_ch -ne 1 ]; then
	sox $data_dir/$wav_name -c 1 $data_dir/ch_tmp.wav
	mv $data_dir/ch_tmp.wav $data_dir/$wav_name; fi
	echo "$wav_name channel changed." >> $log_dir/process.$log_name.log
# Sampling rate should be set to 16000.
wav_sr=`sox --i $data_dir/$wav_name | grep "Sample Rate" | awk '{print $4}'`
if [ $wav_sr -ne 16000 ]; then
	sox $data_dir/$wav_name -r 16000 $data_dir/sr_tmp.wav
	echo "$wav_name sampling rate changed." >> $log_dir/process.$log_name.log
	mv $data_dir/sr_tmp.wav $data_dir/$wav_name; fi

# Extracting MFCC features and calculate CMVN.
$code_dir/make_mfcc.sh --nj $mfcc_nj --cmd "$cmd" $trans_dir $log_dir $data_dir/$mfccdir >> $log_dir/process.$log_name.log
$code_dir/fix_data_dir.sh $trans_dir >> $log_dir/process.$log_name.log
$code_dir/compute_cmvn_stats.sh $trans_dir $log_dir $data_dir/$mfccdir >> $log_dir/process.$log_name.log
$code_dir/fix_data_dir.sh $trans_dir >> $log_dir/process.$log_name.log

## Forced alignment.
# Aligning data. Total 4 trials will be executed to align every audio file. Smaller parameter setting will give the best result 
# but some audio file cannot be aligned with the smaller setting. After 4 trials the audio file will be rejected to be aligned 
# because larger than the 4th parameter setting would not give a adequate result which means that the result cannot be credible.
echo "Force aligning the data." >> $log_dir/process.$log_name.log
for pass in 1 2 3 4; do
	if [ $pass == 1 ]; then
		beam=10
		retry_beam=40
		echo "1st, Beam parameters: beam=$beam, retry_beam=$retry_beam" >> $log_dir/process.$log_name.log
	elif [ $pass == 2 ]; then
		beam=50
		retry_beam=60
		echo "2nd, Beam parameters: beam=$beam, retry_beam=$retry_beam" >> $log_dir/process.$log_name.log
	elif [ $pass == 3 ]; then
		beam=80
		retry_beam=100
		echo "3rd, Beam parameters: beam=$beam, retry_beam=$retry_beam" >> $log_dir/process.$log_name.log
	elif [ $pass == 4 ]; then
		beam=1000
		retry_beam=2500
		echo "4th, Beam parameters: beam=$beam, retry_beam=$retry_beam" >> $log_dir/process.$log_name.log
	elif [ $pass == 5 ]; then
		beam=4000
		retry_beam=8000
		echo "5th, is this audio file long? Beam parameters: beam=$beam, retry_beam=$retry_beam" >> $log_dir/process.$log_name.log
	fi

	# Alignement.
	$code_dir/align_si.sh --nj $align_nj --cmd "$cmd" \
						$trans_dir \
						$lang_dir \
						$fa_model \
						$ali_dir \
						$beam \
						$retry_beam \
						$log_name \
						$log_dir >> $log_dir/process.$log_name.log 2>/dev/null

	# Sanity check.
	# If error occurred, stop alignment right away.
	if [ $pass == 1 ]; then
		error_check=`cat $log_dir/align.$log_name.log | grep "ERROR" | wc -l`
		if [ $error_check != 0 ]; then
			echo -e "Fail Alignment: ERROR has been detected during alignment.\n" >> $log_dir/process.$log_name.log
			fail_num=$((fail_num+1))
			passing=1
			break
		fi
	fi

	# Check the alignemnt result.
	align_check=`cat $log_dir/align.$log_name.log | grep "Did not successfully decode file" | wc -l`
	if [ $align_check == 0 ]; then
		break
	elif [ $align_check == 0 ] && [ $pass == 5 ]; then
		echo "WARNNING: $wav_name was difficult to align, the result might be unsatisfactory." >> $log_dir/process.$log_name.log
	elif [ $align_check != 0 ] && [ $pass == 5 ]; then
		echo -e "Fail Alignment: $wav_name might be corrupted.\n" >> $log_dir/process.$log_name.log
		fail_num=$((fail_num+1))
		passing=1
	fi
done


## Generating textgrid file.
# If the error has not been occurred during alginment, textgrid with respect to audio file will be generated. Otherwise this step will be skipped.
if [ $passing -ne 1 ]; then
	
	# CTM file conversion.
	$kaldi/src/bin/ali-to-phones --ctm-output $fa_model/final.mdl ark:"gunzip -c $ali_dir/ali.1.gz|" - > $ali_dir/raw_ali.ctm 
	echo "ctm result: " >> $log_dir/process.$log_name.log
	# Fixing floating problem.
	python src/local/fix_ctm_float.py $ali_dir/raw_ali.ctm $ali_dir/fixed_ali.ctm
	cat $ali_dir/fixed_ali.ctm >> $log_dir/process.$log_name.log

	# Move requisite files.
	cp $ali_dir/fixed_ali.ctm $result_dir/fixed_ali.txt
	cp $lang_dir/phones.txt $result_dir
	cp $trans_dir/segments $result_dir

	# id to phone conversion.
	echo "Reconstructing the alinged data." >> $log_dir/process.$log_name.log
	python src/local/id2phone.py $result_dir/phones.txt \
								   $result_dir/segments \
								   $result_dir/fixed_ali.txt \
								   $result_dir/final_ali.txt >> $log_dir/process.$log_name.log || exit 1;
	echo "final_ali result: " >> $log_dir/process.$log_name.log
	cat $result_dir/final_ali.txt >> $log_dir/process.$log_name.log

	# Split the whole text files.
	echo "Inserting labels for each column in the aligned data." >> $log_dir/process.$log_name.log
	mkdir -p $result_dir/tmp_fa
	int_line="utt_id\tfile_id\tphone_id\tutt_num\tstart_ph\tdur_ph\tphone\tstart_utt\tend_utt\tstart_real\tend_real\n"
	awk -v fa_var=$int_line 'BEGIN{printf fa_var};{print $0}' $result_dir/final_ali.txt >  $result_dir/tmp_fa/tagged_final_ali.txt
	# cat $result_dir/final_ali.txt | sed '1i '"${int_line}" > $result_dir/tmp_fa/tagged_final_ali.txt

	# Generate text_num file.
	cat $raw_sent_dir/$txt_rename | wc -l >> $raw_sent_dir/text_num.raw || exit 1;

	# Generate Textgrid files and save it to the data directory.
	echo "Organizing the aligned data to textgrid format." >> $log_dir/process.$log_name.log
	# Generate textgrid.
	python src/local/generate_textgrid.py $tg_word_opt $tg_phone_opt \
							$result_dir/tmp_fa \
							$prono_dir/tmp_lexicon.txt \
							$raw_sent_dir/text_num.raw \
							$data_dir 2>/dev/null || align_error=1;
	if [ $align_error -eq 1 ]; then
		echo "Fail Result Composition: $wav_name might be corrupted." | tee -a $log_dir/process.$log_name.log
		# write a fail log to history file.
		echo "$(printf %03d $jidx) FAIL $log_name" >> log/history.log
		align_error=0
		# Redirect log files to main log directory.
		mv $log_dir log/log_$log_name
	else
		echo "$wav_name was successfully aligned." | tee -a $log_dir/process.$log_name.log
		tg_name=`echo $wav_name | sed 's/.wav//g'`
		# write a success log to history file.
		echo "$(printf %03d $jidx) SUCCESS $log_name" >> log/history.log
		mv $data_dir/tagged_final_ali.TextGrid $origin_dir/$tg_name.TextGrid
		# Redirect log files to main log directory.
		mv $log_dir log/log_$log_name
	fi
fi

