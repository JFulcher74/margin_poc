#!/bin/bash

# Revert the main branch to commit fe6c012530438ab657b55aca988c421f814564f9
# This script will reset the branch and force push to GitHub

echo "Resetting main branch to commit fe6c012..."
git reset --hard fe6c012530438ab657b55aca988c421f814564f9

echo "Force pushing to origin main..."
git push origin main --force

echo "Done! The main branch has been reset to commit fe6c012."
