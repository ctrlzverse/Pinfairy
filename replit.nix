# File: replit.nix
{ pkgs }: {
  deps = [
    pkgs.python311Full
    pkgs.playwright-driver
  ];
}