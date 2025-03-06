for file in evaluation/job/profile_mobilenet_large/job_[0-9].yml; do
    number=$(echo "$file" | sed 's/.*job_\([0-9]\)\.yml/\1/')
    new_number=$((number + 10))
    newname="job_${new_number}.yml"
    cp "$file" "evaluation/job/profile_mobilenet_large/$newname"
done