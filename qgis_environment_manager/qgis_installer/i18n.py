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
  "WHICH METHOD?\n\n"
  "A  Official repository — newest QGIS, updated through apt. Debian 12/13/sid, Ubuntu 22.04–26.04 and derivatives (Linux Mint uses its Ubuntu codename).\n"
  "   Debian 12, Ubuntu 22.04 and 24.04 get only the LTR line (their libraries are too old for QGIS 4).\n"
  "B  Flatpak — works on every distribution, sandboxed, installs for your user. Slightly bigger and files access is sandboxed.\n"
  "C  Distribution package — tiny effort, but often an old QGIS.\n\n"
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
},
"ka": {
 "title": "QGIS-ის დაყენება", "lang_btn": "English", "tab_inst": "დაყენება", "tab_guide": "ინსტრუქცია",
 "f_sys": "თქვენი სისტემა", "f_method": "მეთოდი", "f_ver": "ვერსია (ოფიციალური რეპოზიტორია)",
 "f_pkg": "პაკეტები (ოფიციალური რეპოზიტორია)", "log": "ლოგი",
 "mA": "ა. ოფიციალური QGIS რეპოზიტორია (Debian/Ubuntu/Mint) — რეკომენდებული",
 "mB": "ბ. Flatpak (Flathub) — ნებისმიერ დისტრიბუციაზე, მხოლოდ თქვენთვის",
 "mC": "გ. დისტრიბუციის პაკეტი — უმარტივესი, ხშირად ძველი ვერსია",
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
  "რომელი მეთოდი?\n\n"
  "ა  ოფიციალური რეპოზიტორია — ყველაზე ახალი QGIS, განახლება apt-ით. Debian 12/13/sid, Ubuntu 22.04–26.04 და წარმოებულები (Linux Mint-ი თავის Ubuntu-ს კოდურ სახელს იყენებს).\n"
  "   Debian 12-ს, Ubuntu 22.04-სა და 24.04-ს მხოლოდ LTR ხაზი აქვს (ბიბლიოთეკები QGIS 4-ისთვის ძველია).\n"
  "ბ  Flatpak — ნებისმიერ დისტრიბუციაზე მუშაობს, იზოლირებულია, თქვენი მომხმარებლისთვის ყენდება. ცოტა მძიმეა და ფაილებზე წვდომა შეზღუდულია.\n"
  "გ  დისტრიბუციის პაკეტი — უმარტივესი, მაგრამ ხშირად ძველი QGIS.\n\n"
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
    return t("k_data", lang, p=it["path"], sz=it["sz"])


def steps_text(steps, lang="en"):
    out = []
    for s in steps:
        out.append(t("root_note", lang) if s["root"] else t("user_note", lang))
        out.append(s["sh"].rstrip())
        out.append("")
    return "\n".join(out)
