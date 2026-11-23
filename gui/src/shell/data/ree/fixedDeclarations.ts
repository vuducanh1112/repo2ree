const DIGEST = `sha256:${"0".repeat(64)}`;

export const fixedDeclarations = {
  experiment_environment: {
    build_experiment_environment_script_path: "ree-scripts/build_experiment_environment.sh",
    build_experiment_environment_script_digest: DIGEST,
    build_experiment_environment_script_size: 1,
  },
  activate_experiment_environment: {
    activate_experiment_environment_script_path: "ree-scripts/activate_experiment_environment.sh",
    activate_experiment_environment_script_digest: DIGEST,
    activate_experiment_environment_script_size: 1,
  },
  launch: {
    launch_script_path: "ree-scripts/launch.sh",
    launch_script_digest: DIGEST,
    launch_script_size: 1,
  },
  check_working_environment: {
    check_working_environment_script_path: "ree-scripts/check_working_environment.sh",
    check_working_environment_script_digest: DIGEST,
    check_working_environment_script_size: 1,
  },
};
