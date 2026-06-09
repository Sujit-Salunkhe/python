# a = [23,45,43,12]

# minvalue = a[0]

# for i in range(len(a)):
#     if a[i] < minvalue:
#         minvalue = a[i]
    
# print(minvalue)

# b =  [1, 2, 3, 5, 4]

# def findLargestNumber(b):
#     if not b:
#         return None
#     largestValue = b[0]
#     for i in b:
#        if largestValue <= i:
#            largestValue = i
#     return largestValue


# b = findLargestNumber(b)
# print(b)

# def findSecondLargest(b):
#     b = set(b)
#     b=list(b)
#     if not b:
#         return None
#     if len(b) <= 1 :
#         return None
#     largestValue = b[0]
#     secondLargest = b[1]
#     if secondLargest > largestValue:
#         largestValue,secondLargest = secondLargest,largestValue

#     for i in range(2,len(b)):
#         if b[i] > secondLargest:
#             if b[i] > largestValue:
#                 secondLargest = largestValue
#                 largestValue = b[i]
#             elif b[i] == largestValue:
#                 continue
#             else:
#                 secondLargest = b[i]
#     return secondLargest
        
# def findSecondLargest(b):
#     if not b or len(b) < 2:
#         return None
    
#     largest = second = float('-inf')
#     smallest = secondsmallest = float('inf')
    
#     for num in b:
    
#         if num > largest:
#             second = largest
#             largest = num
#         elif num > second and num != largest:
#             second = num
        
     
#         if num < smallest:
#             secondsmallest = smallest
#             smallest = num
#         elif num < secondsmallest and num != smallest:
#             secondsmallest = num

#     has_second_largest = second != float('-inf')
#     has_second_smallest = secondsmallest != float('inf')
    
#     if not has_second_largest and not has_second_smallest:
#         return None
    
#     return (second if has_second_largest else None, 
#             secondsmallest if has_second_smallest else None)

# Test improved version
# print(findSecondLargest([10, 20]))           # (10, 20) ✅
# print(findSecondLargest([1, 1, 2, 2, 3]))    # (2, 2) ✅
# print(findSecondLargest([5, 5, 5, 5]))       # None ✅
# print(findSecondLargest([1, 1, 1, 2]))       # (1, 2) ✅

# d = findSecondLargest(b)
# print(d)

# def isSorted(arr):
#    if not arr or len(arr) < 2:
#        return None
#    for i in range(len(arr) - 1):
#        if arr[i] > arr[i+1]:
#            return False
#    return True
                         
# print(isSorted(arr))

# def isDuplicates(arr):
#     if not  arr or len(arr) < 2:
#         return None
#     seen = {}
#     for x in arr:
#         if x in seen:
#             continue
#         seen[x] = True
#         print(seen)
#     return seen.keys()

# print(isDuplicates([1, 2, 3, 4, 5, 6, 7, 8, 9, 1,11,23]))

# def roateAnArray(arr,num):
#    if not arr :
#        return []
#    elif len(arr) < 2 or num <= 0:
#         return arr
#    recursive = num % len(arr)
#    while recursive > 0:
#        element = arr.pop()
#        arr.insert(0,element) 
#        recursive -=1
#    return arr

# print(roateAnArray(arr,2))

# arr = [5, 4, 3, 2, 1]
# def newRoateAnArray(arr,num):
#     if not arr or len(arr) < 2:
#         return arr[:]
#     newNum = abs(num) % len(arr)
#     if newNum == 0:
#         return arr[:]                
#     elif num > 0:
#         return arr[-newNum:] + arr[:-newNum]
#     else:
#         return arr[newNum:] + arr[:newNum]

# print(newRoateAnArray(arr,-3))
arr = [5, 4, 0, 3, 2, 1, 6, 7, 0, 8, 9, 10, 0, 11, 0]
# def  moveAllTheZeroesToEnd(arr):
#     if not arr or len(arr) < 2:
#         return arr[:]
#     count = 0
#     for i in arr: 
#        if not i:
#            count +=1
#     newArr = [i for i in arr if i]
    
#     return newArr + [0] * (len(arr) - len(newArr))

# print(moveAllTheZeroesToEnd(arr))

# def newMoveAllTheZeroes(arr):
#     if not arr or len(arr) < 2:
#         return arr[:]
#     pos = 0
#     for i in range(len(arr)):
#         if i == pos:
#             continue
#         elif arr[i] != 0:
#             arr[pos],arr[i] = arr[i],arr[pos]
#             pos+=1
#     return arr

# print(newMoveAllTheZeroes(arr))


# def linereSearch(arr,target):
#     if not arr:
#         return -1
#     for i in range(len(arr)):
#         if arr[i] == target:
#             return i
#     return -1


# def findUnionOfTwoArrays(arr1,arr2):
#     seen = {}
#     union = []
#     if not arr1 and not arr2:
#         return []
#     for i in arr1:
#         if i not in seen: 
#             union.append(i)
#             seen[i] = True
#     for i in arr2:
#         if i not in seen: 
#             union.append(i)
#             seen[i] = True
#     return sorted(union)

# def newFindUnionOfTwoArrays(arr1, arr2):
#     seen = set()
#     union = []
#     for x in arr1 + arr2:   
#         if x not in seen and x is not None: 
#             union.append(x)
#             seen.add(x)
#     return union   # no sorting


# def findUnionByPointer(arr1, arr2):
#     i, j = 0, 0
#     union = []
#     while i < len(arr1) and j < len(arr2):
#         if arr1[i] < arr2[j]:
#             if not union or union[-1] != arr1[i]:
#                 union.append(arr1[i])
#             i += 1
#         elif arr1[i] > arr2[j]:
#             if not union or union[-1] != arr2[j]:
#                 union.append(arr2[j])
#             j += 1
#         else:  
#             if not union or union[-1] != arr1[i]:
#                 union.append(arr1[i])
#             i += 1
#             j += 1
   
#     while i < len(arr1):
#         if not union or union[-1] != arr1[i]:
#             union.append(arr1[i])
#         i += 1

#     while j < len(arr2):
#         if not union or union[-1] != arr2[j]:
#             union.append(arr2[j])
#         j += 1
#     return union


# def findInterSectionOfAnArray(arr1,arr2):
#    intersection = []
#    arr1Unique = list(set(arr1))
#    arr2Unique = list(set(arr2))
#    for i in arr2Unique:
#       if i in arr1Unique:
#          intersection.append(i)
#    return intersection
   
# def NewFindInterSectionOfAnArray(arr1,arr2):
#    i,j = 0,0
#    interSection = []
#    while i < len(arr1) and j < len(arr2):
#     if arr1[i] == arr2[j]: 
#         if arr1[i] != interSection[-1]:
#             interSection.append(arr1[i])
#         i+=1
#         j+=1
#     elif arr1[i] < arr2[j]:
#         i +=1
#     else:
#         j +=1
#    return interSection
       
# print(NewFindInterSectionOfAnArray([1,2,3,4,5,5,5,5,6,6,1,11],[1,2,3,4,5,8,11,12,13,14,15,16]))

# def findMissingElement(arr,number):
#     if not arr:
#         return -1
#     for i in range(number - 1):
#         if i+1 != arr[i]:
#             return i+1
        
#     return number

# print(findMissingElement([1,2,3,4,5],6))


# def fineMissingElementByZor(arr,nuber):
#     if not arr:
#         return -1 
#     xor = 0
#     xor2 = 0
#     for x in arr:
#         xor = xor ^ x
#         xor2 = xor2 ^ x+1
#     return xor ^ xor2

# print(fineMissingElementByZor([1,2,3,4,5],6))

# def findConsecutiveOne(arr):
#     if not arr:
#         return 0

#     count = 0
#     max_count = 0

#     for i in arr:
#         if i == 1:
#             count += 1
#             max_count = max(max_count, count)
#         else:
#             count = 0

#     return max_count


# print(findConsecutiveOne([1,1,1,1,1,0,0,1,1,1,1,0,1,1,1,1,1,1,0,1,1,1,0,1,1,1,1,0,1,1,1,1]))

# def findSingleElment(arr):
#     if not arr and len(arr) < 2 :
#         return arr
#     seen = {}
#     for i in arr:
#         if i not in seen:
#             seen[i] = 1
#         else:
#             seen[i] +=1
#     for k,v in seen.items():
#         if v == 1:
#             return k

# def findSingleElementXorVersion(arr):
#     if not arr and len(arr) < 2 :
#         return arr
#     xor = 0
#     for x in arr:
#         xor ^= x
#     return xor 

         
         

# print(findSingleElementXorVersion([1,1,2,2,3,3,4,4,5,5,6,6,7,7,8]))

# def findDoubleSum(arr, target):
#     newArr = []
#     seen = set()

#     for i in range(len(arr)):
#         for j in range(i+1, len(arr)):
#             if arr[i] + arr[j] == target:
#                 pair = tuple(sorted((arr[i], arr[j])))
                
#                 if pair in seen:
#                     continue
                
#                 seen.add(pair)
#                 newArr.append(pair)

#     return newArr

# print(findDoubleSum([1,2,3,4,5,6,7],6))

# def findconsectivearrayfortarget(arr,target):
#     if not arr:
#         return 0
#     i = 0
#     max_length = 0
#     length = 0
#     sum = 0
#     while i < len(arr):
#         sum += arr[i]
#         length +=1
#         if sum == target:
#             max_length = max(max_length,length)
#             sum = 0
#             length = 0
#         elif sum > target:
#             length = 0
#             sum = 0
#         i += 1
#     return max_length


# print(findconsectivearrayfortarget([1,-1,2],2))


# def sortZeroOneTwoValuesArray(arr):
#     if not arr:
#         return arr
#     low = 0
#     mid = 0
#     high = len(arr) - 1
#     while mid <= high:
#         if arr[mid] == 0:
#             arr[low], arr[mid] = arr[mid], arr[low]
#             low += 1
#             mid += 1
#         elif arr[mid] == 2:
#             arr[high], arr[mid] = arr[mid], arr[high]
#             high -= 1
#         else: 
#             mid += 1
#     return arr

# print(sortZeroOneTwoValuesArray([2,0,1,0]))

# def findNumberofArrays(arr):
#     seen = {}
#     if not arr:
#         return None
#     for x in arr:
#         if x not in seen:
#             seen[x] = 1
#         else:
#             seen[x] +=1
#     maxValue = 0
#     for key,value in seen.items():
#         if value > maxValue:
#             maxValue = value
#             newkey = key
#     return (maxValue,newkey)
# print(findNumberofArrays([1,1,1,1,2,2,2,2,3,3,3,3,5,5,5,8,5]))

def maximusSumofSubArray(arr):
    if not arr:
        return None
    maximumsum = 0
    for i in range(len(arr)):
        for j in range(i,len(arr)):
            arrsum = sum(arr[i:j])
            if arrsum > maximumsum:
                maximumsum = arrsum
    return maximumsum 
    

# def kadanesAlgoritheme(arr):
#     if not arr:
#         return None
#     sum = float('-inf')
#     maximum = 0
#     for i in arr:
#         sum += i

#         if  sum > maximum:
#             maximum = sum
#         if  sum < 0:
#             sum = 0
#     return maximum        
    

# print(kadanesAlgoritheme([-2,-3,3,4,9,-9,-1,-2,1,5,2,-3,2,3,25]))

# def kadanes_algorithm(arr):
#     if not arr:
#         return None
#     max_sum = arr[0]
#     current_sum = arr[0]
#     for num in arr[1:]:
#         current_sum = max(num, current_sum + num) 
#         max_sum = max(max_sum, current_sum)
#     return max_sum
# print(kadanes_algorithm([-2,-3,3,4,9,-9,-1,-2,1,5,2,-3,2,3,25]))

# def rearrangMinusAndPlusValues(arr):
#     minus = []
#     plus =[]
#     newArr = []
#     if not arr:
#         return arr
#     for i in arr:
#         if i < 0:
#             minus.append(i)
#         else:
#             plus.append(i)
#     p = 0
#     m = 0
#     for i in range(len(arr)):
#         if i % 2  == 0:
#             newArr.insert(i,plus[p])
#             p +=1
#         elif i % 2 != 0 :

#             newArr.insert(i,minus[m]) 
#             m += 1
#         else:
#             newArr.append(0)
#     return newArr


# def betterrearrange(arr):
#     if not arr:
#         return None
#     even = 0
#     odd = 1
#     while even < len(arr) and odd < len(arr):
#         if arr[even] > 0:
#             even +=2
#         elif arr[odd] < 0:
#             odd +=2
#         else:
#             arr[even],arr[odd] = arr[odd],arr[even]

#     if len(arr) % 2 != 0 and arr [-1] < 0:
#         arr.insert(even,0)
#     return arr
# print( int(199/10) )
import math
def extractNumbers(n):
    while n > 0:
        numbers = n % 10
        print(numbers)
        n = int(n/10)

# extractNumbers(10987)

# def logoften(n):
#     count = math.log10(n)
#     print(int(count+1))

# logoften(456543459)

# def checkReverseisSame(n):
#     dup = 0
#     m = n
#     while m > 0:
#         dup = dup * 10 + m % 10
#         m =  m//10 
#     return dup == n

# def CheckForArmStrongNumber(n):
#     check = 0
#     m = n
#     while n > 0:
#         k = n % 10
#         n //=10
#         check += k ** 3
#     print(check == m)


# def finddivisors(n):
#   i = 1
#   arr =[]
#   while i <= i * i <=n:
#       if(n % i  == 0):
#         arr.append(i)
#         if((n/i) != 1):
#           arr.append(n//i)
#       i +=1
#   return arr  
      

# print(finddivisors(15))
    
    
    
# CheckForArmStrongNumber(35)

# print(betterrearrange([3,1,-2,-5,6,-7,10,-90,34,-84,13,-78,67]))


def FindLeaderInArray(arr):
    if arr is None:
        return None
    newArr=[]

    for i in range(len(arr)):
        count = 0
        for j in range(i+1,len(arr)):
            if arr[i] > arr[j]:
                count +=1
            if count >= len(arr) - i - 1:
                newArr.append(arr[i])
        if i == len(arr) -1:
            newArr.append(arr[i])
    return newArr

# print(FindLeaderInArray([10,22,12,3,0,6]))


def findleaderInArray2(arr):
    if arr is None:
        return None
    new_leaders = []
    leader = arr[-1]
    new_leaders.append(leader) 
    for i in range(len(arr),0,-1):
        value = arr[i - 1]
        if value > leader:
            new_leaders.append(value)
            leader = value
    return new_leaders[::-1]

# print(findleaderInArray2([10,22,12,3,0,6,45,4,2])) 

def findLongestConsecativeSequence(arr):
    longest = 1
    new_arr = list(set(arr))
    hash_map = {}
    if new_arr is None:
        return None
    for i in arr:
       hash_map[i]
    for i in range(i):
        pass


def setZerosInMatrix(arr):
    arr2=[]
    for i in range(len(arr)):
        for j in range(len(arr[i])):
            if arr[i][j] == 0:
                arr2.append((i,j))
    for i in range(len(arr2)):
        k,m = arr2[i]
        for i in range(len(arr)):
            arr[i][m] = 0
        for j in range(len(arr[k])):
            arr[k][j] = 0
    return arr
  

print(setZerosInMatrix([[1,1,1,1],[1,0,0,1],[1,1,0,1],[1,1,1,1]]))
     