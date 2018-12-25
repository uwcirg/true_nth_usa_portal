#!/bin/sh -e

cmdname="$(basename "$0")"
repo_root="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
   cat << USAGE >&2
Usage:
   ${cmdname} [-h] [--help]

   -h
   --help
          Show this help message

    Transform translations from PO format to i18next JSON format
USAGE
}

if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    usage
    exit 0
fi

PATH="${PATH}:${repo_root}/bin"

echo "Converting translations from PO to JSON format"
gulp-wrapper.sh i18nextConvertPOToJSON

echo "Combining front-end and back-end translation files"
gulp-wrapper.sh combineTranslationJsons
