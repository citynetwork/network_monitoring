#!/bin/sh

for A in *.py lib/*.py; do
	res=$(pyflakes $A)
	if [ $? -ne 0 ]; then
	  echo $res
	  echo
	  echo
	fi
done
