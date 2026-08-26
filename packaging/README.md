# Packaging — repo-wide packager

ფლაგინების ZIP-ები **ხელით აღარ ედება**. `pages.yml` workflow ყოველ push-ზე
(და ყოველდღე) აშენებს მათ ავტომატურად და პირდაპირ Pages-ზე აქვეყნებს.
PAT/write უფლება არ სჭირდება — git-ში არაფერი იბიძგება.

## როგორ მუშაობს

`packaging/build_site.py` კითხულობს [`manifest.json`](manifest.json)-ს და თითო
ფლაგინს ერთ-ერთი გზით აწყობს:

| ტიპი | რას ნიშნავს |
|------|-------------|
| `src`      | ამ რეპოს ფოლდერი იფუთება ZIP-ად (top-folder = ფოლდერის სახელი) |
| `repo`     | გარე public რეპოდან იკლონება და `files`-ით მითითებული ფაილები იფუთება |
| `prebuilt` | `plugins/<zip>` უცვლელად რჩება (გამონაკლისები) |

ყოველთვის გამოტოვდება `__pycache__` და `*.pyc`. `exclude`-ით შეიძლება ქვე-ფოლდერის
გამორიცხვა (მაგ. `georgian_cadastre` → `files`). ZIP დეტერმინისტულია.

ასევე: `plugins.xml`-ის თითო ჩანაწერის `version` ავტომატურად სწორდება ფლაგინის
`metadata.txt`-იდან (აღწერებს არ ეხება).

## ახალი ფლაგინის დამატება

1. ჩააგდე source ფოლდერი რეპოში (ან გამოიყენე `repo` გარე რეპოსთვის).
2. დაამატე ჩანაწერი `manifest.json`-ში და `plugins.xml`-ში.
3. push — დანარჩენს workflow აკეთებს.

## შემოწმება

```bash
python packaging/build_site.py --verify     # აწყობილი vs არსებული zip-ები
python packaging/build_site.py --out _site  # სრული საიტის ლოკალური აწყობა
```
