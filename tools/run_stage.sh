#!bash

SCRIPT=$1
STAGE=$2

if [ -e $SCRIPT ]; then
  source $SCRIPT
else
  echo "File $SCRIPT doesn't existing"
  exit
fi

echo "Running $SCRIPT $STAGE stage";
$($STAGE)

# case $STAGE in
#   "post_install" ) 
#       echo "Running $SCRIPT post_install stage";
#       post_install ;;
#   "post_update" ) 
#       echo "Running $SCRIPT post_update stage";
#       post_update ;;
# esac

