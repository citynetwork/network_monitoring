#!/bin/sh

for A in *.py lib/*.py graphite/*.py; do
	res=$(pycodestyle $A)
	if [ $? -ne 0 ]; then
	  echo $res
	  echo
	  echo
	fi
done
