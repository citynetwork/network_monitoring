#!/bin/sh

for A in *.py lib/*.py; do
	echo "$A:"
	pycodestyle $A | grep -vE 'E(501|402)'
	echo
	echo
done
