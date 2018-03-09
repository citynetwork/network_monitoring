#!/bin/sh

for A in $(ls | grep -E '\.py$'); do
	echo "$A:"
	pycodestyle $A | grep -vE 'E(501|402)'
	echo
	echo
done
