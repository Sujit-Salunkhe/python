def fizzbuzz(n):
    fizzbuzzarr = []
    if n == 0:
        return [0]
    for i in range(1,n+1):
        if (i % 15 == 0):
            fizzbuzzarr.append("FizzBuzz")
        elif(i % 3 == 0):
            fizzbuzzarr.append("Fizz")
        elif(i % 5 == 0):
            fizzbuzzarr.append("Buzz")
        else:
            fizzbuzzarr.append(i)
    return fizzbuzzarr

# print(fizzbuzz(15))

def countOdds(low,high):
    odds = 0
    for i in range(low,high+1):
      if i % 2 == 0:
         pass
      else:
        odds += 1 
    
    return odds

# print(countOdds(3,9)) 

def countOdds2(low,high):
    odds = 0
    if low % 2 == 0:
        if high % 2 == 0:
            for _ in range(low+1,high,2):
                odds+=1
        else:
            for _ in range(low+1 ,high+1,2):
                odds+=1
    else:
        for _ in range(low,high+1,2):
        
            odds+=1
    return odds

# print(countOdds2(3,7))
# print(countOdds2(3,10))
# print(countOdds2(2,10))
# print(countOdds2(3,12))
# print(countOdds2(8,10))
print(countOdds(3,7))
