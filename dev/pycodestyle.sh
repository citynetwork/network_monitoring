#!/bin/sh

for A in $(ls | grep -E '\.py$'); do
	echo "$A:"
	pycodestyle $A | grep -v E501
	echo
	echo
done
