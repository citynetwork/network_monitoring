#!/bin/sh

for A in *.py lib/*.py; do
	echo "$A:"
	pyflakes $A
	echo
	echo
done
