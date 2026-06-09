rotateMatrix = [[1,2,3,4],[5,6,7,8],[9,10,11,12],[13,14,15,16]]
matrix_4x4 = [
    [1,  2,  3,  4],
    [5,  6,  7,  8],
    [9,  10, 11, 12],
    [13, 14, 15, 16]
]

matrix_4x4_2 = [
    [10, 20, 30, 40],
    [50, 60, 70, 80],
    [90, 11, 12, 13],
    [14, 15, 16, 17]
]

matrix_4x4_3 = [
    ['A', 'B', 'C', 'D'],
    ['E', 'F', 'G', 'H'],
    ['I', 'J', 'K', 'L'],
    ['M', 'N', 'O', 'P']
]

matrix_5x5_5 = [
    [1,  2,  3,  4,  5],
    [6,  7,  8,  9,  10],
    [11, 12, 13, 14, 15],
    [16, 17, 18, 19, 20],
    [21, 22, 23, 24, 25]
]



# def rotateAMatriby90Degree(matrix,n):
#     answer = [[0 for _ in range(n)]for _ in range(n)]
#     for i in range(len(matrix)):
#       for j in range(len(matrix)):
#         answer[j][n-1-i] = matrix[i][j]
#     return answer

# output =  rotateAMatriby90Degree(rotateMatrix,4)

# for i in output:
#     print(*i)


# def rotateaMatri90Degree2(matrix):
#     for i in range(len(matrix)):
#         for j in range(i + 1,len(matrix)):
#             matrix[i][j], matrix[j][i] = matrix[j][i],matrix[i][j]
#             print("matrix Values :",matrix[i][j],matrix[j][i])
#     for i in  range(len(matrix)):
#        matrix[i] = matrix[i][::-1]
#     return matrix

# output = rotateaMatri90Degree2(rotateMatrix)
# for i in output:
#     print(*i)


# def printSpiralMatrix(matrix):
#     start = 0
#     size = len(matrix)
#     for p in range(size):
#         for i in range(size):
#             print(matrix[start][i])
#         for j in range(start+1,size):
#             print(matrix[j][size - start+1])
#         for k in range(size+2,size+2):
#             print(matrix[size-1][size - k])
#         for l in range(len(matrix) - size):
#             print(matrix[len(matrix)][matrix])
# printSpiralMatrix(matrix_6x6)
matrix_6x6 = [
    [1,  2,  3,  4,  5,  6],
    [7,  8,  9,  10, 11, 12],
    [13, 14, 15, 16, 17, 18],
    [19, 20, 21, 22, 23, 24],
    [25, 26, 27, 28, 29, 30],
    [31, 32, 33, 34, 35, 36]
]

def printSpiralMatrix(matrix):
    start = 0
    end = len(matrix) - 1
    length = len(matrix)
    for k in range(len(matrix)//2):
        
        for i in range(start,length - 1):
            print(matrix[start][i],end=" ")
        for i in range(start,length -1):
            print(matrix[i][end],end=" ")
        for i in range(length-1,start,-1):
            print(matrix[end][i],end=" ")
        for i in range(length-1,start,-1):
            print(matrix[i][start],end=" ")

        start+=1
        end -=1
        length -=2
        print()

# printSpiralMatrix(matrix_6x6)

def countsubarrays(arr,k):
    count = 0
    sum=0
    for i in range(len(arr)):
        sum = 0
        for j in range(i,len(arr)):
            sum += arr[j]
            if sum == 3:
                count+=1
    return count


arr1 = [1,2,3,-3,1,1,1,4,2,-3]
subarrays = countsubarrays(arr1,3)
# print(subarrays)

def countSubarrayUsingPrefixSum(arr, k):
    count = 0
    current_sum = 0
    hashmap = {0: 1} 
    
    for i in range(len(arr)):
        current_sum += arr[i]
        target = current_sum - k
        if target in hashmap:
            count += hashmap[target]            
        if current_sum in hashmap:
            hashmap[current_sum] += 1
        else:
            hashmap[current_sum] = 1
    return count

print(countSubarrayUsingPrefixSum(arr1,3))