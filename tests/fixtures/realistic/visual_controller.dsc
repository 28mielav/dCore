visual_controller:
  type: world
  debug: false
  events:
    on player clicks block:
    - determine passively cancelled
    - narrate "<player.name> activated the visual controller."
    - run visual_transition

visual_transition:
  type: task
  script:
  - define shader_stage bloom
  - wait 2t
  - narrate "Applying <[shader_stage]> visual stage."
  - stop
