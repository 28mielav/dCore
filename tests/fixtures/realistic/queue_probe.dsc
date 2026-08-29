queue_probe:
  type: task
  script:
  - run missing_transition
  - while true:
    - wait 1t
    - narrate "pulse"
