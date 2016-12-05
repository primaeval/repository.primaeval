import hashlib
import sys
name = sys.argv[1]
md5 = hashlib.md5(open(name, 'rb').read()).hexdigest()
f = open(name+".md5","wb")
f.write(md5)
f.close()