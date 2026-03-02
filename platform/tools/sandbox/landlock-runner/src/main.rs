//! landlock-runner — SF Agent Filesystem Sandbox
//!
//! Usage:
//!   landlock-runner <workspace_path> -- <command> [args...]
//!
//! Restricts the child process to:
//!   RW: workspace_path (agent's project workspace only)
//!   RO: /bin /sbin /usr /lib /lib64 /etc /tmp /proc (system tools)
//!   DENY: everything else (platform source, other workspaces, secrets)
//!
//! Exits with the child process exit code.
//! On kernels without Landlock support, falls back to direct exec (no sandbox).

use std::env;
use std::os::unix::process::CommandExt;
use std::path::PathBuf;
use std::process;

use landlock::{
    Access, AccessFs, PathBeneath, PathFd, Ruleset, RulesetAttr, RulesetCreatedAttr, RulesetStatus,
    ABI,
};

/// Directories that agents need read access to (system tools, libraries, etc.)
const RO_PATHS: &[&str] = &[
    "/bin",
    "/sbin",
    "/usr",
    "/lib",
    "/lib64",
    "/lib32",
    "/libx32",
    "/etc",
    "/proc",
    "/sys/fs",
    "/dev/null",
    "/dev/urandom",
    "/dev/random",
];

/// Directories that agents need read-write access to (scratch, tmp output)
const RW_SHARED: &[&str] = &["/tmp"];

fn main() {
    let args: Vec<String> = env::args().collect();

    // Parse args: landlock-runner <workspace> -- <cmd> [args...]
    if args.len() < 4 {
        eprintln!(
            "Usage: landlock-runner <workspace_path> -- <command> [args...]\n\
             Example: landlock-runner /app/workspaces/proj-abc -- bash -c 'ls -la'"
        );
        process::exit(1);
    }

    let workspace = PathBuf::from(&args[1]);

    // Find "--" separator
    let sep_pos = args
        .iter()
        .position(|a| a == "--")
        .unwrap_or_else(|| {
            eprintln!("Error: missing '--' separator between workspace and command");
            process::exit(1);
        });

    if sep_pos + 1 >= args.len() {
        eprintln!("Error: no command after '--'");
        process::exit(1);
    }

    let cmd = &args[sep_pos + 1];
    let cmd_args = &args[sep_pos + 2..];

    // Validate workspace exists
    if !workspace.exists() {
        eprintln!(
            "Error: workspace '{}' does not exist",
            workspace.display()
        );
        process::exit(1);
    }

    let workspace_abs = workspace.canonicalize().unwrap_or(workspace.clone());

    // Apply Landlock rules
    match apply_sandbox(&workspace_abs) {
        Ok(status) => {
            match status {
                RulesetStatus::FullyEnforced => {
                    // Good — all rules applied
                }
                RulesetStatus::PartiallyEnforced => {
                    eprintln!("[landlock-runner] WARNING: partially enforced (older kernel ABI)");
                }
                RulesetStatus::NotEnforced => {
                    eprintln!("[landlock-runner] WARNING: Landlock not supported by kernel — running WITHOUT sandbox");
                }
            }
        }
        Err(e) => {
            eprintln!("[landlock-runner] ERROR applying sandbox: {e} — running WITHOUT sandbox");
        }
    }

    // Exec the command (replaces current process)
    let err = process::Command::new(cmd).args(cmd_args).exec();
    eprintln!("[landlock-runner] exec failed: {err}");
    process::exit(127);
}

fn apply_sandbox(workspace: &PathBuf) -> Result<RulesetStatus, Box<dyn std::error::Error>> {
    // Use best supported ABI — landlock crate auto-downgrades to highest supported ABI
    let abi = ABI::V3;

    let ro_access = AccessFs::from_read(abi);
    let rw_access = AccessFs::from_all(abi);

    let mut ruleset = Ruleset::default()
        .handle_access(AccessFs::from_all(abi))?
        .create()?;

    // Agent workspace: full RW
    ruleset = ruleset.add_rule(PathBeneath::new(PathFd::new(workspace)?, rw_access))?;

    // Shared /tmp: full RW
    for p in RW_SHARED {
        let path = PathBuf::from(p);
        if path.exists() {
            if let Ok(fd) = PathFd::new(&path) {
                ruleset = ruleset.add_rule(PathBeneath::new(fd, rw_access))?;
            }
        }
    }

    // System dirs: read-only
    for p in RO_PATHS {
        let path = PathBuf::from(p);
        if path.exists() {
            if let Ok(fd) = PathFd::new(&path) {
                ruleset = ruleset.add_rule(PathBeneath::new(fd, ro_access))?;
            }
        }
    }

    let status = ruleset.restrict_self()?;
    Ok(status.ruleset)
}
