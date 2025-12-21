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
# print(countOdds(3,7))

nums1= [9,4,5,3,2,1,3]

# def smallerNumbersThanCurrent(nums):
#     numbers=[]
#     for i in nums:
#         big=0
#         for j in nums:
#             if i > j:
#                 big+=1
#         numbers.append(big)
#     return numbers


# print(smallerNumbersThanCurrent(nums1))

nums=7
# a = str(nums)[0]
# print(type(a))
# print(type,"s")


def countDigits(num):
    mystr = str(num)
    count = 0
    for i in mystr:
        if i == 0:
            pass
        if num % int(i) == 0:
            count +=1
    return count
            
# print(countDigits(nums))

def countDigits2(num):
    count = 0
    temp = num
    
    while temp>0:
        r = temp  % 10
        if num % r == 0 :
            count +=1
        temp //= 10
    return count
    
# print(countDigits2(nums))


def factorial(n):
    if n == 1:
        return 1
    return n*factorial(n-1)

def fib(n):
  if n == 0 or n==1:
      return n
  return fib(n-1) + fib(n-2)

print(fib(3))
def factorial(n):
    if n == 1:
        return 1
    return n*factorial(n-1)

def fib(n):
  if n == 0 or n==1:
      return n
  return fib(n-1) + fib(n-2)

print(fib(3))
def factorial(n):
    if n == 1:
        return 1
    return n*factorial(n-1)

def fib(n):
  if n == 0 or n==1:
      return n
  return fib(n-1) + fib(n-2)

print(fib(3))
def factorial(n):
    if n == 1:
        return 1
    return n*factorial(n-1)

def fib(n):
  if n == 0 or n==1:
      return n
  return fib(n-1) + fib(n-2)

print(fib(3))
def factorial(n):
    if n == 1:
        return 1
    return n*factorial(n-1)

def fib(n):
  if n == 0 or n==1:
      return n
  return fib(n-1) + fib(n-2)

print(fib(3))

