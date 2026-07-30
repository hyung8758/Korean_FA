# Configure PATH and locale for the packaged KoreanFA runtime and a Kaldi engine.
# The optional first argument is the root of a compatible Kaldi installation.

root=${1:-}
runtime_root=${KOREANFA_RUNTIME_ROOT:-$PWD}
#valgrind=yes
valgrind=no

# If you run with valgrind, by setting valgrind=yes above, 
# the errors can be seen with the following command:
# ( grep 'ERROR SUMMARY' exp/*/*.log | grep -v '0 errors' ;  grep 'definitely lost' exp/*/*.log | grep -v -w 0 )

if [ "$valgrind" = "no" ]; then
  export PATH=${root}/src/bin:${root}/tools/openfst/bin:${root}/src/fstbin/:${root}/src/gmmbin/:${root}/src/featbin/:${root}/src/fgmmbin:${root}/src/sgmmbin:${root}/src/lm:${root}/src/latbin:${root}/src/online2bin:${root}/src/ivectorbin:${root}/src/nnet3bin:$PATH
else 
  mkdir bin
  for x in ${root}/src/{bin,fstbin,gmmbin,featbin,fgmmbin,sgmmbin,lm,latbin}; do
    for y in $x/*; do
      if [ -x $y ]; then
        b=`basename $y`
        echo valgrind $y '"$@"' > bin/$b
        chmod +x bin/`basename $b`
      fi
    done
  done
  export PATH=`pwd`/bin/:${root}/tools/openfst/bin:$PATH
fi

# Use the POSIX locale for deterministic shell sorting on both GNU/Linux and
# macOS.  Python reads Korean and Japanese resources explicitly as UTF-8.
export LC_ALL=C
export LANG=C
export PATH=$PATH:$runtime_root/pipeline:$runtime_root/pipeline/core:$root/src/nnet2bin:$root/src/sgmm2bin
