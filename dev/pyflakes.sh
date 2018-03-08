#!/bin/sh

for A in $(ls | grep -E '\.py$'); do
	echo "$A:"
	pyflakes $A
	echo
	echo
done
