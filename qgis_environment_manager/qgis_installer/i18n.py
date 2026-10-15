"""English / Georgian texts of the installer and the helpers that use them. No UI toolkit."""
import os

from .system import KEYRING, KEY_FPR, SOURCES

STR = {
"en": {
 "title": "QGIS Installer", "lang_btn": "ქართული", "tab_inst": "Install", "tab_guide": "Guide",
 "f_sys": "Your system", "f_method": "Method", "f_ver": "Version (official repository)",
 "f_pkg": "Packages (official repository)", "log": "Log",
 "mA": "A. Official QGIS repository (Debian/Ubuntu/Mint) — recommended",
 "mB": "B. Flatpak (Flathub) — any distribution, your user only",
"mC": "C. Distribution package — simplest, usually older",
 "k_container": "Container {tool}: {name} (QGIS lives inside; removing it deletes the container's own files)",
 "ch_latest": "Latest release {v}", "ch_ltr": "Long-term release (LTR) {v} — most stable",
 "ch_nightly-release": "Nightly of the next point release", "ch_nightly-ltr": "Nightly of the next LTR point release",
 "ch_nightly": "Nightly development (master) — unstable, debug build",
 "p_grass": "GRASS plugin (qgis-plugin-grass)", "p_server": "QGIS Server (qgis-server)",
 "p_python": "Python plugin support (python3-qgis)",
 "preview": "Preview & install…", "remove": "Uninstall…", "copy": "Copy commands",
 "sys_line": "{name} • codename: {code} • arch: {arch} • package manager: {pm}",
 "st_ok": "✔ Official repository supports this system.",
 "st_ltr": "ℹ This release has only the LTR line in the official repository (dependencies are not QGIS 4 ready).",
 "st_unsup": "⚠ This system is not in the official repository list — use Flatpak (B) or the distribution package (C).",
 "st_nodeb": "ℹ Not Debian/Ubuntu-based — the official apt repository does not apply. Use Flatpak (B) or the distribution package (C).",
 "st_arch": "⚠ The official repository is built for amd64 only.",
 "st_inst": "Installed now: {v}", "st_none": "QGIS is not installed (apt).",
 "confirm_title": "Review before running", "will_run": "These commands will run:",
 "root_note": "# runs as administrator (a password prompt appears)", "user_note": "# runs as your user",
 "run": "Run", "cancel": "Cancel", "done_ok": "Finished successfully. Find QGIS in the application menu.",
 "done_fail": "A step failed (exit code {rc}). See the log.",
 "elev_fail": "Could not get administrator rights automatically.\nRun this in a terminal instead:\n\n{cmd}",
 "copied": "Commands copied to the clipboard.", "running": "Running…",
 "no_method": "This method is not available on your system.",
 "rm_title": "Uninstall QGIS", "tab_rm": "Uninstall / switch version",
 "rm_goto": "Uninstall / switch version…", "rm_scan": "Rescan", "rm_sel": "Remove selected…",
 "rm_none": "No QGIS installation found (apt, repository files, Flatpak, Snap, distro package, user data).",
 "rm_found": "Found — tick what to remove:", "rm_opts": "Options",
 "rm_purge": "Also delete system configuration files (apt purge)", "rm_auto": "Remove unused dependencies afterwards (autoremove)",
 "rm_next": "After removal, open the Install tab (to choose another version)",
 "rm_data_warn": "⚠ User data = your QGIS profiles, settings, installed plugins. Deleted permanently, not ticked by default.",
 "rm_nothing": "Nothing selected.",
 "k_apt": "apt packages: {n} (qgis {v}) — source: {o}", "k_repo": "QGIS apt repository files: {f}{c}",
 "k_flatpak": "Flatpak ({i}) org.qgis.qgis {v}", "k_snap": "Snap: qgis {v}", "k_dist": "Distribution package ({pm}): qgis {v}",
 "k_data": "User data: {p} ({sz})", "k_unknown": "unknown",
 "guide": (
  "WHICH WAY?\n\n"
  "Say what you want and the program recommends the best way for your system, with the reason. You can pick any other way by hand.\n"
  "• Stable and long-term (LTR) - fewest surprises; best for work and teaching.\n"
  "• Newest release - newest features (a new major version can be rough in its first months).\n"
  "• Next to my QGIS - try QGIS 4 without touching the one you have (Flatpak or a container).\n\n"
  "Official repository (Debian 12/13/sid, Ubuntu 22.04-26.04, Mint) - updated through apt; Debian 12, Ubuntu 22.04 and 24.04 get only the LTR line. "
  "Flatpak - every distribution, sandboxed; branch stable is QGIS 4, branch lts is the old QGIS 3 line on an end-of-life runtime. "
  "Fedora, openSUSE, Arch, Mageia - the distribution's own package (Arch also has the AUR: built from source). "
  "Fedora Atomic - rpm-ostree layering (reboot needed). Containers (Distrobox, Toolbx) - QGIS in its own box. Spack - builds everything from source. "
  "NixOS and Slackware - instructions only, nothing is changed for you.\n"
  "Under each way the program says how far it was checked: installed for real in a container, package names and a dry run in a container, "
  "or only taken from the installation guide (not run by the author).\n\n"
  "CHANNELS\n\n"
  "• Latest release — newest features (new major version first months can be rough).\n"
  "• LTR (long-term) — fewer changes, best for work and teaching.\n"
  "• Nightly — rebuilt daily, may break. Not for production.\n\n"
  "WHAT METHOD A DOES\n\n"
  "1. installs wget, gnupg, ca-certificates\n"
  "2. downloads the QGIS signing key and CHECKS its fingerprint (" + KEY_FPR + ") — aborts on mismatch\n"
  "3. installs it to " + KEYRING + "\n"
  "4. writes " + SOURCES + " (your codename + chosen channel)\n"
  "5. apt update, then installs the packages you ticked\n\n"
  "TROUBLESHOOTING\n\n"
  "• Remove QGIS from other sources first (distribution packages, other PPAs) to avoid conflicts.\n"
  "• “NO_PUBKEY”/key errors: the signing key expires 2027-08-08 — download a newer key from qgis.org.\n"
  "• Repository 404 after a distro upgrade: use Uninstall…, then install again for the new codename.\n"
  "• Administrator prompt does not appear: the app shows the commands to paste in a terminal.\n\n"
  "SWITCHING VERSION\n\n"
  "Use the Uninstall tab: it finds every QGIS (apt, repository files, Flatpak, Snap, distro package, user data), you tick what to remove, then choose another version in the Install tab. Going from a newer to an older line (e.g. latest → LTR) needs the old one removed first — apt will not downgrade."),
 "rq_head": "Requirements of {plugin}", "rq_present": "installed", "rq_missing": "missing",
 "rq_optional": "optional", "rq_manual": "no package for your system: install {name} by hand",
 "rq_none": "{plugin} needs nothing from the operating system.",
 "rq_all_ok": "Everything needed is already installed.",
 "rq_unknown_plugin": "Unknown plugin '{plugin}'. Known: {known}",
 "rc_apt-official": "Official QGIS repository (Debian / Ubuntu / Mint…)",
 "rc_apt-distro": "Distribution package (apt)",
 "rc_flatpak": "Flatpak (Flathub)",
 "rc_dnf-fedora": "Fedora package (dnf)",
 "rc_rpm-ostree-fedora": "Fedora Atomic (rpm-ostree)",
 "rc_zypper-opensuse": "openSUSE package (zypper)",
 "rc_pacman-arch": "Arch Linux package (pacman)",
 "rc_aur-helper": "Arch User Repository (AUR): builds from source",
 "rc_urpmi-mageia": "Mageia package (urpmi)",
 "rc_spack": "Spack: builds everything from source",
 "rc_distrobox": "Distrobox container (openSUSE Tumbleweed)",
 "rc_toolbx": "Toolbx container (Fedora)",
 "rc_nix-manual": "NixOS (instructions)",
 "rc_slackware-manual": "Slackware (instructions)",
 "rcn_no_apt": "needs a Debian/Ubuntu based system with apt",
 "rcn_codename": "this release is not in the official repository's list",
 "rcn_arch": "the official repository is built for amd64 only",
 "rcn_no_flatpak": "Flatpak is missing and no package manager was found to install it",
 "rcn_not_fedora": "needs Fedora",
 "rcn_immutable": "this is an immutable system: use Flatpak or a container",
 "rcn_no_dnf": "dnf was not found",
 "rcn_not_atomic": "needs a Fedora Atomic Desktop with rpm-ostree",
 "rcn_not_opensuse": "needs openSUSE",
 "rcn_no_zypper": "zypper was not found",
 "rcn_not_arch": "needs Arch Linux or a derivative",
 "rcn_no_pacman": "pacman was not found",
 "rcn_no_aur_helper": "needs an AUR helper (yay or paru)",
 "rcn_not_mageia": "needs Mageia (the successor of Mandriva)",
 "rcn_no_urpmi": "urpmi was not found",
 "rcn_no_spack": "Spack is not installed",
 "rcn_no_distrobox": "Distrobox is not installed",
 "rcn_no_toolbox": "Toolbx is not installed",
 "rcn_not_nixos": "only for NixOS",
 "rcn_not_slackware": "only for Slackware",
 "rcw_apt_other_sources": "Remove QGIS and GRASS packages installed from other repositories first (the guide asks for this).",
 "rcw_apt_ubuntugis": "Builds that use the ubuntugis libraries also exist for Ubuntu 22.04 and 24.04 (see the guide); they are not offered here.",
 "rcw_distro_older": "Distribution packages are often older than the official repository.",
 "rcw_flatpak_portal": "Some systems also need xdg-desktop-portal plus xdg-desktop-portal-gtk, -kde or -cosmic for file dialogs.",
 "rcw_flatpak_pip": "Extra Python modules for plugins: flatpak run --devel --command=pip3 org.qgis.qgis install NAME --user",
 "rcw_flatpak_lts_eol": "The LTR Flatpak (branch lts) is built on an end-of-life Qt 5.15 runtime.",
 "rcw_fedora_version": "The version is the one your Fedora release carries (check with: dnf info qgis).",
 "rcw_ostree_reboot": "rpm-ostree changes apply after a reboot.",
 "rcw_ostree_flatpak": "The guide recommends Flatpak on Atomic Desktops.",
 "rcw_suse_no_ltr": "openSUSE has no separate LTR package (qgis-ltr is not in the repositories): use the Flatpak lts branch or a container for the LTR.",
 "rcw_arch_no_ltr": "The official repository carries the latest line only; LTR and git are in the AUR.",
 "rcw_aur_build": "AUR packages are built from source on your computer from a build recipe anyone can submit: read it before you build. Runs as your user.",
 "rcw_mageia_names": "The guide's old Mandriva line says qgis-python; Mageia has qgis and qgis-grass.",
 "rcw_spack_long": "Spack builds QGIS and all its dependencies from source: it can take hours.",
 "rcw_spack_load": "Afterwards run: spack load qgis, then qgis",
 "rcw_box_alongside": "Runs in a separate container: your current QGIS is not touched.",
 "rcw_box_update_distrobox": "Update later with: distrobox upgrade --all",
 "rcw_box_toolbx_launch": "Toolbx does not add a menu entry: start with: toolbox run --container qgis-box qgis",
 "rcw_nix_config": "Nothing is changed for you: copy the snippet into configuration.nix yourself and rebuild.",
 "rcm_nix_try": "Try it without installing",
 "rcm_nix_config": "configuration.nix (system install)",
 "rcm_nix_python": "Extra Python packages",
 "rcm_slackware_builds": "SlackBuilds (build scripts for Slackware)",
 "why_apt_ltr": "The official repository gives you the long-term release (LTR) with normal apt updates.",
 "why_distro_tracks_release": "Your distribution's own package is the simplest and is maintained for your release.",
 "why_flatpak_lts": "Flatpak works on every system; the lts branch is the long-term QGIS 3 line.",
 "why_apt_latest": "The official repository has the newest release for your system.",
 "why_rolling_latest": "Your distribution ships the newest QGIS in its own repositories.",
 "why_flatpak_stable": "Flatpak gives you the newest QGIS (the stable branch) on any system.",
 "why_alongside_flatpak": "Flatpak is isolated: QGIS 4 runs next to your current QGIS and does not change it.",
 "why_alongside_box": "A container keeps the new QGIS apart from your system.",
 "why_nothing_fits": "No recipe fits this system. See the installation guide: {url}",
 "goal_stable": "Stable and long-term (LTR)",
 "goal_latest": "Newest release",
 "goal_alongside": "Try QGIS 4 next to my QGIS",
 "vf_container": "package names and a dry run were checked in a container",
 "vf_real": "installed for real in a container",
 "vf_flathub": "the Flathub branches were checked",
 "vf_guide": "steps taken from the guide; not run by the author",
 "vf_names": "package names exist; the install was not run",
 "vf_manual": "instructions only",
 "rc_manual_only": "Nothing to run: follow the instructions above.",
 "rc_unknown": "Unknown recipe '{recipe}'. Known: {known}",
 "rc_not_applicable": "Recipe {recipe} does not apply here: {why}",
 "f_goal": "What do you want?", "f_recipe": "Way to install", "f_ropts": "Options",
 "recommended": "Recommended for your system: {name}.",
 "o_channel": "Version", "o_branch": "Flatpak branch", "o_scope": "Install for",
 "o_geo": "Also add the openSUSE Application:Geo repository",
 "br_stable": "stable - the newest QGIS (QGIS 4)", "br_lts": "lts - long-term QGIS 3 (old runtime, no longer maintained)",
 "sc_user": "my user only (no password needed)", "sc_system": "the whole system",
 "aur_ltr": "qgis-ltr - long-term release (built from source)", "aur_testing": "qgis-git - development version (built from source)",
 "nixch_latest": "qgis - newest", "nixch_ltr": "qgis-ltr - long-term",
 "cat_cli": "Command line tools", "cat_engine": "GIS engines", "cat_python": "Python libraries", "cat_db": "Database clients",
 "cp_unknown": "Unknown component '{id}'. Known: {known}",
 "cp_have": "{name}: already installed.",
 "cp_no_pm": "No supported package manager was found on this system.",
 "upd_title": "Update the QGIS installations found here",
 "rcw_upd_close_qgis": "Close QGIS before updating: its libraries change under it. Your profile (settings, plugins) is not touched; a copy of it is a cheap safety net.",
 "rcw_upd_none": "Nothing to update here: no QGIS installation was found, or only user data and repository files.",
 "rcw_upd_container": "The QGIS in the container qgis-box is updated inside it with the container's own package manager (for example: distrobox enter qgis-box -- sudo zypper --non-interactive update qgis).",
 "rcw_upd_ostree": "rpm-ostree upgrades the whole system image; the update applies after a reboot.",
 "rcw_upd_arch_full": "Arch does not support updating one package: the whole system is updated (a partial upgrade can break it). Run it yourself when you have time.",
 "rcw_upd_unknown": "No update command is known for this package manager.",
 "rcm_upd_arch": "Update the system (includes QGIS)", "rcm_upd_aur": "Update the AUR package",
},
"ka": {
 "title": "QGIS-ის დაყენება", "lang_btn": "English", "tab_inst": "დაყენება", "tab_guide": "ინსტრუქცია",
 "f_sys": "თქვენი სისტემა", "f_method": "მეთოდი", "f_ver": "ვერსია (ოფიციალური რეპოზიტორია)",
 "f_pkg": "პაკეტები (ოფიციალური რეპოზიტორია)", "log": "ლოგი",
 "mA": "ა. ოფიციალური QGIS რეპოზიტორია (Debian/Ubuntu/Mint) — რეკომენდებული",
 "mB": "ბ. Flatpak (Flathub) — ნებისმიერ დისტრიბუციაზე, მხოლოდ თქვენთვის",
"mC": "გ. დისტრიბუციის პაკეტი — უმარტივესი, ხშირად ძველი ვერსია",
 "k_container": "კონტეინერი {tool}: {name} (QGIS შიგნითაა; წაშლისას კონტეინერის საკუთარი ფაილებიც იკარგება)",
 "ch_latest": "უახლესი რელიზი {v}", "ch_ltr": "გრძელვადიანი რელიზი (LTR) {v} — ყველაზე სტაბილური",
 "ch_nightly-release": "შემდეგი point-რელიზის ღამის ბილდი", "ch_nightly-ltr": "შემდეგი LTR point-რელიზის ღამის ბილდი",
 "ch_nightly": "განვითარების ღამის ბილდი (master) — არასტაბილური, debug",
 "p_grass": "GRASS დანამატი (qgis-plugin-grass)", "p_server": "QGIS Server (qgis-server)",
 "p_python": "Python დანამატების მხარდაჭერა (python3-qgis)",
 "preview": "ნახვა და დაყენება…", "remove": "წაშლა…", "copy": "ბრძანებების კოპირება",
 "sys_line": "{name} • კოდური სახელი: {code} • არქიტექტურა: {arch} • პაკეტ-მენეჯერი: {pm}",
 "st_ok": "✔ ოფიციალური რეპოზიტორია ამ სისტემას უჭერს მხარს.",
 "st_ltr": "ℹ ამ სისტემისთვის ოფიციალურ რეპოზიტორიაში მხოლოდ LTR ხაზია (ბიბლიოთეკები QGIS 4-ისთვის მზად არ არის).",
 "st_unsup": "⚠ ეს სისტემა ოფიციალური რეპოზიტორიის სიაში არ არის — გამოიყენეთ Flatpak (ბ) ან დისტრიბუციის პაკეტი (გ).",
 "st_nodeb": "ℹ სისტემა Debian/Ubuntu-ზე დაფუძნებული არ არის — ოფიციალური apt რეპოზიტორია არ გამოდგება. გამოიყენეთ Flatpak (ბ) ან დისტრიბუციის პაკეტი (გ).",
 "st_arch": "⚠ ოფიციალური რეპოზიტორია მხოლოდ amd64-ისთვისაა.",
 "st_inst": "ახლა დაყენებულია: {v}", "st_none": "QGIS დაყენებული არ არის (apt).",
 "confirm_title": "გადახედეთ გაშვებამდე", "will_run": "შესრულდება ეს ბრძანებები:",
 "root_note": "# ადმინისტრატორის უფლებით (გამოჩნდება პაროლის ფანჯარა)", "user_note": "# თქვენი მომხმარებლით",
 "run": "გაშვება", "cancel": "გაუქმება", "done_ok": "წარმატებით დასრულდა. QGIS მოძებნეთ აპლიკაციების მენიუში.",
 "done_fail": "ერთი ნაბიჯი ჩავარდა (კოდი {rc}). იხილეთ ლოგი.",
 "elev_fail": "ადმინისტრატორის უფლება ავტომატურად ვერ მივიღე.\nგაუშვით ტერმინალში:\n\n{cmd}",
 "copied": "ბრძანებები დაკოპირდა.", "running": "სრულდება…",
 "no_method": "ეს მეთოდი თქვენს სისტემაზე ხელმისაწვდომი არ არის.",
 "rm_title": "QGIS-ის წაშლა", "tab_rm": "წაშლა / ვერსიის შეცვლა",
 "rm_goto": "წაშლა / ვერსიის შეცვლა…", "rm_scan": "თავიდან ძებნა", "rm_sel": "მონიშნულის წაშლა…",
 "rm_none": "QGIS-ის არცერთი ინსტალაცია ვერ მოიძებნა (apt, რეპოზიტორიის ფაილები, Flatpak, Snap, დისტრიბუციის პაკეტი, მომხმარებლის მონაცემები).",
 "rm_found": "ნაპოვნია — მონიშნეთ რისი წაშლაც გინდათ:", "rm_opts": "პარამეტრები",
 "rm_purge": "სისტემური კონფიგურაციის ფაილებიც წაიშალოს (apt purge)", "rm_auto": "შემდეგ წაიშალოს გამოუყენებელი დამოკიდებულებები (autoremove)",
 "rm_next": "წაშლის შემდეგ გაიხსნას „დაყენება“ (სხვა ვერსიის ასარჩევად)",
 "rm_data_warn": "⚠ მომხმარებლის მონაცემები = თქვენი QGIS პროფილები, პარამეტრები, დაყენებული დანამატები. იშლება სამუდამოდ, ნაგულისხმევად მონიშნული არ არის.",
 "rm_nothing": "არაფერია მონიშნული.",
 "k_apt": "apt პაკეტები: {n} (qgis {v}) — წყარო: {o}", "k_repo": "QGIS apt რეპოზიტორიის ფაილები: {f}{c}",
 "k_flatpak": "Flatpak ({i}) org.qgis.qgis {v}", "k_snap": "Snap: qgis {v}", "k_dist": "დისტრიბუციის პაკეტი ({pm}): qgis {v}",
 "k_data": "მომხმარებლის მონაცემები: {p} ({sz})", "k_unknown": "უცნობი",
 "guide": (
  "რომელი გზა?\n\n"
  "თქვენ ამბობთ, რა გსურთ და პროგრამა თქვენი სისტემისთვის საუკეთესო გზას გირჩევთ მიზეზითურთ. ნებისმიერი სხვა გზის ხელით არჩევაც შეგიძლიათ.\n"
  "• სტაბილური და გრძელვადიანი (LTR) - ყველაზე ნაკლები სიურპრიზი, სამუშაოსა და სწავლებისთვის საუკეთესო.\n"
  "• უახლესი გამოშვება - ახალი შესაძლებლობები (ახალი მთავარი ვერსია პირველ თვეებში შეიძლება უხეში იყოს).\n"
  "• ჩემი QGIS-ის გვერდით - QGIS 4-ის საცდელად, ახლანდელის შეხების გარეშე (Flatpak ან კონტეინერი).\n\n"
  "ოფიციალური რეპოზიტორია (Debian 12/13/sid, Ubuntu 22.04-26.04, Mint) - ახლდება apt-ით. Debian 12-ს, Ubuntu 22.04-სა და 24.04-ს მხოლოდ LTR ხაზი აქვს. "
  "Flatpak - ნებისმიერ დისტრიბუციაზე, იზოლირებული. შტო stable არის QGIS 4, შტო lts კი ძველი QGIS 3 ხაზი უკვე აღარ მხარდაჭერილ გარემოზე. "
  "Fedora, openSUSE, Arch, Mageia - დისტრიბუციის საკუთარი პაკეტი (Arch-ს აქვს AUR-იც, რომელიც წყაროდან იგება). "
  "Fedora Atomic - rpm-ostree-ით (საჭიროა გადატვირთვა). კონტეინერები (Distrobox, Toolbx) - QGIS საკუთარ ყუთში. Spack - ყველაფერს წყაროდან აგებს. "
  "NixOS და Slackware - მხოლოდ ინსტრუქცია, თქვენთვის არაფერი იცვლება.\n"
  "თითოეულ გზას პროგრამა წერს, რამდენად არის შემოწმებული: კონტეინერში ნამდვილად დაყენდა, პაკეტების სახელები და სატესტო გაშვება კონტეინერში, "
  "ან მხოლოდ სახელმძღვანელოდანაა აღებული (ავტორს არ გაუშვია).\n\n"
  "არხები\n\n"
  "• უახლესი რელიზი — ახალი შესაძლებლობები (ახალი მაჟორული ვერსიის პირველ თვეებში შეიძლება უხეში იყოს).\n"
  "• LTR (გრძელვადიანი) — ნაკლები ცვლილება, სამუშაოსა და სწავლებისთვის საუკეთესო.\n"
  "• Nightly — ყოველდღე ახლდება, შეიძლება გაფუჭდეს. სამუშაოსთვის არ ვარგა.\n\n"
  "რას აკეთებს მეთოდი „ა“\n\n"
  "1. აყენებს wget, gnupg, ca-certificates\n"
  "2. ჩამოტვირთავს QGIS-ის ხელმოწერის გასაღებს და ამოწმებს თითის ანაბეჭდს (" + KEY_FPR + ") — შეუსაბამობისას წყდება\n"
  "3. ათავსებს აქ: " + KEYRING + "\n"
  "4. წერს " + SOURCES + " (თქვენი კოდური სახელი + არჩეული არხი)\n"
  "5. apt update, შემდეგ აყენებს მონიშნულ პაკეტებს\n\n"
  "პრობლემები\n\n"
  "• ჯერ წაშალეთ QGIS სხვა წყაროებიდან (დისტრიბუციის პაკეტები, სხვა PPA), კონფლიქტი რომ არ მოხდეს.\n"
  "• „NO_PUBKEY“/გასაღების შეცდომა: გასაღები 2027-08-08-ს იწურება — qgis.org-დან ახალი გადმოწერეთ.\n"
  "• 404 დისტრიბუციის განახლების შემდეგ: „წაშლა…“, მერე ახალი კოდური სახელით თავიდან დააყენეთ.\n"
  "• ადმინისტრატორის ფანჯარა არ ჩანს: აპი აჩვენებს ბრძანებებს ტერმინალში ჩასასმელად.\n\n"
  "ვერსიის შეცვლა\n\n"
  "გამოიყენეთ „წაშლა“ ჩანართი: ის პოულობს ყველა QGIS-ს (apt, რეპოზიტორიის ფაილები, Flatpak, Snap, დისტრიბუციის პაკეტი, მომხმარებლის მონაცემები), მონიშნავთ რისი წაშლაც გინდათ, მერე „დაყენება“ ჩანართში სხვა ვერსიას არჩევთ. ახალი ხაზიდან ძველზე (მაგ. უახლესი → LTR) გადასვლისას ჯერ ძველი უნდა წაიშალოს — apt ვერსიას არ დააქვეითებს."),
 "rq_head": "{plugin}: მოთხოვნები", "rq_present": "დაყენებულია", "rq_missing": "აკლია",
 "rq_optional": "არასავალდებულო", "rq_manual": "თქვენი სისტემისთვის პაკეტი არ არის: {name} ხელით დააყენეთ",
 "rq_none": "{plugin}-ს ოპერაციული სისტემიდან არაფერი სჭირდება.",
 "rq_all_ok": "ყველაფერი საჭირო უკვე დაყენებულია.",
 "rq_unknown_plugin": "უცნობი დანამატი „{plugin}“. ცნობილია: {known}",
 "rc_apt-official": "ოფიციალური QGIS-ის რეპოზიტორია (Debian / Ubuntu / Mint…)",
 "rc_apt-distro": "დისტრიბუციის პაკეტი (apt)",
 "rc_flatpak": "Flatpak (Flathub)",
 "rc_dnf-fedora": "Fedora-ს პაკეტი (dnf)",
 "rc_rpm-ostree-fedora": "Fedora Atomic (rpm-ostree)",
 "rc_zypper-opensuse": "openSUSE-ს პაკეტი (zypper)",
 "rc_pacman-arch": "Arch Linux-ის პაკეტი (pacman)",
 "rc_aur-helper": "Arch User Repository (AUR): წყაროდან აგებს",
 "rc_urpmi-mageia": "Mageia-ს პაკეტი (urpmi)",
 "rc_spack": "Spack: ყველაფერს წყაროდან აგებს",
 "rc_distrobox": "Distrobox კონტეინერი (openSUSE Tumbleweed)",
 "rc_toolbx": "Toolbx კონტეინერი (Fedora)",
 "rc_nix-manual": "NixOS (ინსტრუქცია)",
 "rc_slackware-manual": "Slackware (ინსტრუქცია)",
 "rcn_no_apt": "საჭიროა Debian/Ubuntu-ზე დაფუძნებული სისტემა apt-ით",
 "rcn_codename": "ეს გამოშვება ოფიციალური რეპოზიტორიის სიაში არ არის",
 "rcn_arch": "ოფიციალური რეპოზიტორია მხოლოდ amd64-ისთვისაა",
 "rcn_no_flatpak": "Flatpak არ არის და მისი დასაყენებელი პაკეტების მმართველი ვერ ვიპოვეთ",
 "rcn_not_fedora": "საჭიროა Fedora",
 "rcn_immutable": "ეს უცვლელი (immutable) სისტემაა: გამოიყენეთ Flatpak ან კონტეინერი",
 "rcn_no_dnf": "dnf ვერ მოიძებნა",
 "rcn_not_atomic": "საჭიროა Fedora Atomic Desktop rpm-ostree-ით",
 "rcn_not_opensuse": "საჭიროა openSUSE",
 "rcn_no_zypper": "zypper ვერ მოიძებნა",
 "rcn_not_arch": "საჭიროა Arch Linux ან მისი წარმოებული",
 "rcn_no_pacman": "pacman ვერ მოიძებნა",
 "rcn_no_aur_helper": "საჭიროა AUR-ის დამხმარე (yay ან paru)",
 "rcn_not_mageia": "საჭიროა Mageia (Mandriva-ს მემკვიდრე)",
 "rcn_no_urpmi": "urpmi ვერ მოიძებნა",
 "rcn_no_spack": "Spack დაყენებული არ არის",
 "rcn_no_distrobox": "Distrobox დაყენებული არ არის",
 "rcn_no_toolbox": "Toolbx დაყენებული არ არის",
 "rcn_not_nixos": "მხოლოდ NixOS-ისთვის",
 "rcn_not_slackware": "მხოლოდ Slackware-ისთვის",
 "rcw_apt_other_sources": "ჯერ წაშალეთ QGIS-ისა და GRASS-ის პაკეტები, რომლებიც სხვა რეპოზიტორიებიდანაა დაყენებული (ამას სახელმძღვანელო ითხოვს).",
 "rcw_apt_ubuntugis": "Ubuntu 22.04-სა და 24.04-ისთვის არსებობს ubuntugis-ის ბიბლიოთეკებზე აგებული ვერსიებიც (იხილეთ სახელმძღვანელო). აქ ისინი არ არის შემოთავაზებული.",
 "rcw_distro_older": "დისტრიბუციის პაკეტები ხშირად ოფიციალურ რეპოზიტორიაზე ძველია.",
 "rcw_flatpak_portal": "ზოგ სისტემას ფაილის ფანჯრებისთვის xdg-desktop-portal და მასთან xdg-desktop-portal-gtk, -kde ან -cosmic სჭირდება.",
 "rcw_flatpak_pip": "დანამატებისთვის დამატებითი Python-მოდულები: flatpak run --devel --command=pip3 org.qgis.qgis install NAME --user",
 "rcw_flatpak_lts_eol": "LTR Flatpak (შტო lts) ვადაგასულ Qt 5.15 გარემოზეა აგებული.",
 "rcw_fedora_version": "ვერსია ისაა, რასაც თქვენი Fedora-ს გამოშვება შეიცავს (შეამოწმეთ: dnf info qgis).",
 "rcw_ostree_reboot": "rpm-ostree-ის ცვლილებები გადატვირთვის შემდეგ ამოქმედდება.",
 "rcw_ostree_flatpak": "Atomic Desktops-ზე სახელმძღვანელო Flatpak-ს გირჩევთ.",
 "rcw_suse_no_ltr": "openSUSE-ს ცალკე LTR პაკეტი არ აქვს (qgis-ltr რეპოზიტორიებში არ არის): LTR-ისთვის გამოიყენეთ Flatpak-ის lts შტო ან კონტეინერი.",
 "rcw_arch_no_ltr": "ოფიციალურ რეპოში მხოლოდ უახლესი ხაზია; LTR და git AUR-შია.",
 "rcw_aur_build": "AUR-ის პაკეტები თქვენს კომპიუტერზე იგება წყაროდან ისეთი რეცეპტით, რომლის გამოქვეყნებაც ნებისმიერს შეუძლია. აგებამდე წაიკითხეთ. გაეშვება თქვენი მომხმარებლით.",
 "rcw_mageia_names": "სახელმძღვანელოს ძველ Mandriva-ს სტრიქონში qgis-python წერია; Mageia-ში qgis და qgis-grass არის.",
 "rcw_spack_long": "Spack QGIS-სა და ყველა დამოკიდებულებას წყაროდან აგებს: შეიძლება საათები დასჭირდეს.",
 "rcw_spack_load": "მერე გაუშვით: spack load qgis, შემდეგ qgis",
 "rcw_box_alongside": "ცალკე კონტეინერში მუშაობს: თქვენს ახლანდელ QGIS-ს არ ეხება.",
 "rcw_box_update_distrobox": "მოგვიანებით განახლება: distrobox upgrade --all",
 "rcw_box_toolbx_launch": "Toolbx მენიუს ჩანაწერს არ ამატებს: გაუშვით: toolbox run --container qgis-box qgis",
 "rcw_nix_config": "თქვენთვის არაფერი იცვლება: ფრაგმენტი თავად ჩასვით configuration.nix-ში და ხელახლა ააგეთ სისტემა.",
 "rcm_nix_try": "სცადეთ დაყენების გარეშე",
 "rcm_nix_config": "configuration.nix (სისტემაში დაყენება)",
 "rcm_nix_python": "დამატებითი Python-პაკეტები",
 "rcm_slackware_builds": "SlackBuilds (Slackware-ის ასაგები სკრიპტები)",
 "why_apt_ltr": "ოფიციალური რეპოზიტორია გრძელვადიან გამოშვებას (LTR) და ჩვეულებრივ apt-განახლებებს გაძლევთ.",
 "why_distro_tracks_release": "თქვენი დისტრიბუციის პაკეტი ყველაზე მარტივია და თქვენი გამოშვებისთვის მოვლილია.",
 "why_flatpak_lts": "Flatpak ყველა სისტემაზე მუშაობს; lts შტო გრძელვადიანი QGIS 3-ის ხაზია.",
 "why_apt_latest": "ოფიციალურ რეპოზიტორიაში თქვენი სისტემისთვის უახლესი გამოშვებაა.",
 "why_rolling_latest": "თქვენი დისტრიბუცია უახლეს QGIS-ს საკუთარ რეპოებში აწვდის.",
 "why_flatpak_stable": "Flatpak ნებისმიერ სისტემაზე უახლეს QGIS-ს (stable შტო) გაძლევთ.",
 "why_alongside_flatpak": "Flatpak იზოლირებულია: QGIS 4 თქვენს ახლანდელ QGIS-თან ერთად მუშაობს და მას არ ცვლის.",
 "why_alongside_box": "კონტეინერი ახალ QGIS-ს თქვენი სისტემისგან გამოყოფს.",
 "why_nothing_fits": "ამ სისტემას არცერთი რეცეპტი არ ერგება. იხილეთ სახელმძღვანელო: {url}",
 "goal_stable": "სტაბილური და გრძელვადიანი (LTR)",
 "goal_latest": "უახლესი გამოშვება",
 "goal_alongside": "QGIS 4-ის გვერდიგვერდ საცდელად",
 "vf_container": "პაკეტების სახელები და სატესტო გაშვება კონტეინერში შემოწმდა",
 "vf_real": "კონტეინერში ნამდვილად დაყენდა",
 "vf_flathub": "Flathub-ის შტოები შემოწმდა",
 "vf_guide": "ნაბიჯები სახელმძღვანელოდანაა; ავტორს არ გაუშვია",
 "vf_names": "პაკეტების სახელები არსებობს; დაყენება არ გაშვებულა",
 "vf_manual": "მხოლოდ ინსტრუქცია",
 "rc_manual_only": "გასაშვები არაფერია: მიჰყევით ზემოთ მოცემულ ინსტრუქციას.",
 "rc_unknown": "უცნობი რეცეპტი „{recipe}“. ცნობილია: {known}",
 "rc_not_applicable": "რეცეპტი {recipe} აქ არ გამოდგება: {why}",
 "f_goal": "რა გსურთ?", "f_recipe": "დაყენების გზა", "f_ropts": "პარამეტრები",
 "recommended": "თქვენი სისტემისთვის რეკომენდებულია: {name}.",
 "o_channel": "ვერსია", "o_branch": "Flatpak-ის შტო", "o_scope": "ვისთვის დაყენდეს",
 "o_geo": "openSUSE-ის Application:Geo რეპოზიტორიაც დაემატოს",
 "br_stable": "stable - უახლესი QGIS (QGIS 4)", "br_lts": "lts - გრძელვადიანი QGIS 3 (ძველი გარემო, აღარ ახლდება)",
 "sc_user": "მხოლოდ ჩემთვის (პაროლი არ სჭირდება)", "sc_system": "მთელი სისტემისთვის",
 "aur_ltr": "qgis-ltr - გრძელვადიანი გამოშვება (იგება წყაროდან)", "aur_testing": "qgis-git - სატესტო ვერსია (იგება წყაროდან)",
 "nixch_latest": "qgis - უახლესი", "nixch_ltr": "qgis-ltr - გრძელვადიანი",
 "cat_cli": "ბრძანების სტრიქონის ხელსაწყოები", "cat_engine": "GIS-ის ძრავები", "cat_python": "Python-ის ბიბლიოთეკები", "cat_db": "მონაცემთა ბაზის კლიენტები",
 "cp_unknown": "უცნობი კომპონენტი „{id}“. ცნობილია: {known}",
 "cp_have": "{name}: უკვე დაყენებულია.",
 "cp_no_pm": "ამ სისტემაზე მხარდაჭერილი პაკეტების მმართველი ვერ მოიძებნა.",
 "upd_title": "აქ ნაპოვნი QGIS-ის განახლება",
 "rcw_upd_close_qgis": "განახლებამდე დახურეთ QGIS: მისი ბიბლიოთეკები მის ქვეშ იცვლება. თქვენი პროფილი (პარამეტრები, დანამატები) არ შეიცვლება, მისი ასლი იაფი დაზღვევაა.",
 "rcw_upd_none": "აქ განახლებადი არაფერია: QGIS-ის დაყენება ვერ ვიპოვე ან მხოლოდ მომხმარებლის მონაცემები და რეპოზიტორიის ფაილებია.",
 "rcw_upd_container": "კონტეინერ qgis-box-ში QGIS მის შიგნით ახლდება კონტეინერის საკუთარი პაკეტების მმართველით (მაგალითად: distrobox enter qgis-box -- sudo zypper --non-interactive update qgis).",
 "rcw_upd_ostree": "rpm-ostree მთელ სისტემურ ხატს ანახლებს; განახლება გადატვირთვის შემდეგ ამოქმედდება.",
 "rcw_upd_arch_full": "Arch-ზე ერთი პაკეტის განახლება მხარდაჭერილი არ არის: ახლდება მთელი სისტემა (ნაწილობრივმა განახლებამ სისტემა შეიძლება დააზიანოს). გაუშვით თავად, როცა დრო გექნებათ.",
 "rcw_upd_unknown": "ამ პაკეტების მმართველისთვის განახლების ბრძანება უცნობია.",
 "rcm_upd_arch": "სისტემის განახლება (QGIS-ის ჩათვლით)", "rcm_upd_aur": "AUR-ის პაკეტის განახლება",
},
}


def t(key, lang="en", **kw):
    s = STR.get(lang, STR["en"])[key]
    return s.format(**kw) if kw else s


def label_for(it, lang="en"):
    k = it["kind"]
    if k == "apt":
        return t("k_apt", lang, n=len(it["pkgs"]), v=it["v"], o=it["o"] or t("k_unknown", lang))
    if k == "repo":
        return t("k_repo", lang, f=", ".join(os.path.basename(f) for f in it["files"]), c=it["c"])
    if k == "flatpak":
        return t("k_flatpak", lang, i=it["i"], v=it["v"])
    if k == "snap":
        return t("k_snap", lang, v=it["v"])
    if k == "dist":
        return t("k_dist", lang, pm=it["pm"], v=it["v"])
    if k == "container":
        return t("k_container", lang, tool=it["tool"], name=it["name"])
    return t("k_data", lang, p=it["path"], sz=it["sz"])


def steps_text(steps, lang="en"):
    out = []
    for s in steps:
        out.append(t("root_note", lang) if s["root"] else t("user_note", lang))
        out.append(s["sh"].rstrip())
        out.append("")
    return "\n".join(out)
