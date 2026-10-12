#!/usr/bin/env bash

set -e

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
if project_root=$(git -C "$PWD" rev-parse --show-toplevel 2>/dev/null); then
    :
else
    project_root=$PWD
fi

source_root="$script_dir/specify"
target_root="$project_root/.specify"
refreshed_scripts=0
refreshed_templates=0
created_configs=0
preserved_configs=0

mkdir -p "$target_root/scripts/bash" "$target_root/templates"

for source_file in "$source_root/scripts/bash"/*.sh; do
    [ -f "$source_file" ] || continue
    destination="$target_root/scripts/bash/$(basename "$source_file")"
    cp "$source_file" "$destination"
    chmod +x "$destination"
    refreshed_scripts=$((refreshed_scripts + 1))
done

for source_file in "$source_root/templates"/*.md; do
    [ -f "$source_file" ] || continue
    cp "$source_file" "$target_root/templates/"
    refreshed_templates=$((refreshed_templates + 1))
done

copy_if_missing() {
    source_file=$1
    destination=$2
    if [ -e "$destination" ]; then
        preserved_configs=$((preserved_configs + 1))
    else
        cp "$source_file" "$destination"
        created_configs=$((created_configs + 1))
    fi
}

mkdir -p "$target_root/memory"
copy_if_missing "$source_root/memory/constitution.md" "$target_root/memory/constitution.md"
copy_if_missing "$source_root/init-options.json" "$target_root/init-options.json"
copy_if_missing "$source_root/integration.json" "$target_root/integration.json"
copy_if_missing "$source_root/.gitignore" "$target_root/.gitignore"

printf 'Spec Kit bootstrap: %s\n' "$project_root"
printf 'Refreshed %s scripts and %s templates.\n' "$refreshed_scripts" "$refreshed_templates"
printf 'Created %s configuration files; preserved %s existing configuration files.\n' \
    "$created_configs" "$preserved_configs"
