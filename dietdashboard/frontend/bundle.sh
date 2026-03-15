#!/bin/sh

if [ "$1" = "watch" ]; then
  trap "kill 0" EXIT
  esbuild js/generic_index.js --outfile=../static/generic_bundle.js --bundle --format=esm --platform=browser --watch=forever &
  esbuild styles.css --outfile=../static/bundle.css --watch=forever &
  wait
else
  esbuild js/generic_index.js --outfile=../static/generic_bundle.js --bundle --format=esm --platform=browser --minify
  esbuild styles.css --outfile=../static/bundle.css --minify
fi
