n=100 
m=280 
s=2 
s=s-1
while n < m:
    m = m - n
pri=s+m

print(pri)
while m > 0:
    m-=1
    print("m",m)
    if (s==n):
        s=1
    else:
        s+=1
    print("s",s)


print(s)
s=s-1
while m > 0:
    m-=1
    if (s==n):
        s=1
    else:
        s+=1
print (s)

