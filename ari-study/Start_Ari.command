#!/bin/sh
cd "$(dirname "$0")" || exit 1
npm run build && npm start
