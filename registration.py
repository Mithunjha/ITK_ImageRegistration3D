
import sys
import itk
import matplotlib.pyplot as plt

if len(sys.argv) != 4:
    print("Input format : !python filename.py <fixedImagePath> <MovingImagePath> <Outputfolderpath>")
    sys.exit(1)

fixedImageFile = sys.argv[1]
print(fixedImageFile)
movingImageFile = sys.argv[2]
outputImageFile = sys.argv[3] + "/registered.vtk"
differenceImageAfterFile = sys.argv[3] + "/difference_after.vtk" 
differenceImageBeforeFile = sys.argv[3] + "/difference_before.vtk" 

PixelType = itk.F

fixedImage = itk.imread(fixedImageFile, PixelType)
movingImage = itk.imread(movingImageFile, PixelType)

Dimension = fixedImage.GetImageDimension() 

FixedImageType = itk.Image[PixelType, Dimension]
MovingImageType = itk.Image[PixelType, Dimension]


print(f"Shape of fixed image : {fixedImage.shape}")
print(f"Shape of moving image : {movingImage.shape}")
print(f"Dimension : {Dimension}")
print(f"ITKImageType of fixed image : {FixedImageType}")
print(f"ITKImageType of moving image : {MovingImageType}")

###############################################################################################
############### Initialize the main components of ITK frame work ##############################
###############################################################################################

TransformType = itk.TranslationTransform[itk.D, Dimension] # translation transformation
initialTransform = TransformType.New()

optimizer = itk.RegularStepGradientDescentOptimizerv4.New(LearningRate=4,         #Gradient descent
                                                          MinimumStepLength=0.001,
                                                          RelaxationFactor=0.5,
                                                          NumberOfIterations=100)


############### Interpolator ####################
interpolator = itk.LinearInterpolateImageFunction[FixedImageType,itk.D]
fixed_interpolator = interpolator.New()
moving_interpolator = interpolator.New()


# can choose between 2 metrics - mutual information metric is more viable for this task
# to enable MSE uncomment below code

# metric = itk.MeanSquaresImageToImageMetricv4[FixedImageType, MovingImageType].New()

# comment below code to enable MSE error
metric = itk.MattesMutualInformationImageToImageMetricv4[FixedImageType, MovingImageType].New() #Mutual information as metric
numberOfBins = 24
metric.SetNumberOfHistogramBins(numberOfBins)
metric.SetUseMovingImageGradientFilter(False)
metric.SetUseFixedImageGradientFilter(False)
metric.SetFixedInterpolator(fixed_interpolator)
metric.SetMovingInterpolator(moving_interpolator)


registration = itk.ImageRegistrationMethodv4[FixedImageType,MovingImageType].New(FixedImage=fixedImage,
                                                                                 MovingImage=movingImage,
                                                                                 Metric=metric,
                                                                                 Optimizer=optimizer,
                                                                                 InitialTransform=initialTransform)

movingInitialTransform = TransformType.New()
initialParameters = movingInitialTransform.GetParameters()
initialParameters[0] = 0  # identity matrix is set as initial transofrmation for both fixed an moving image
initialParameters[1] = 0
movingInitialTransform.SetParameters(initialParameters)
registration.SetMovingInitialTransform(movingInitialTransform)

identityTransform = TransformType.New()
identityTransform.SetIdentity()
registration.SetFixedInitialTransform(identityTransform)


## Enable multi scale registration by modifying below codes
# registration.SetNumberOfLevels(1)
# registration.SetSmoothingSigmasPerLevel([0]) 
# registration.SetShrinkFactorsPerLevel([1])

## example : (uncomment below section to enable multi scale registration)

registration.SetNumberOfLevels(3)
registration.SetSmoothingSigmasPerLevel([0,0,0]) #smoothing factor per level
registration.SetShrinkFactorsPerLevel([1,2,3]) #shrink factor per level


## enable the observer to trace the intermediate optimizer values

iter = []
value = []
def iterationUpdate():
    currentParameter = registration.GetTransform().GetParameters()
    iter.append(optimizer.GetCurrentIteration())
    value.append(optimizer.GetValue())
    print(
        "Index : %i -->  Metric : %f   (X,Y,Z) : (%f %f %f)"
        % (
            optimizer.GetCurrentIteration(),
            optimizer.GetValue(),
            currentParameter.GetElement(0),
            currentParameter.GetElement(1),
            currentParameter.GetElement(2),

        )
    )
    

iterationCommand = itk.PyCommand.New()
iterationCommand.SetCommandCallable(iterationUpdate)
optimizer.AddObserver(itk.IterationEvent(), iterationCommand)

print("==========================Starting registration==========================")

registration.Update()

############ set translation parameters ##################
transform = registration.GetTransform()
finalParameters = transform.GetParameters()
translationAlongX = finalParameters.GetElement(0)
translationAlongY = finalParameters.GetElement(1)
translationAlongZ = finalParameters.GetElement(2)

########### get final parameters ######################
numberOfIterations = optimizer.GetCurrentIteration()
bestValue = optimizer.GetValue()

print("============================Registration done============================")
print("============================Final parameters=============================")
print("Result = ")
print(" Translation X = " + str(translationAlongX))
print(" Translation Y = " + str(translationAlongY))
print(" Translation Z = " + str(translationAlongZ))
print(" Iterations    = " + str(numberOfIterations))
print(" Metric value  = " + str(bestValue))
print("=========================================================================")

######## set composite transformation #############
CompositeTransformType = itk.CompositeTransform[itk.D, Dimension]
outputCompositeTransform = CompositeTransformType.New()
outputCompositeTransform.AddTransform(movingInitialTransform)
outputCompositeTransform.AddTransform(registration.GetModifiableTransform())

####### set resampler parameters ##############
resampler = itk.ResampleImageFilter.New(Input=movingImage,
        Transform=outputCompositeTransform,
        UseReferenceImage=True,
        ReferenceImage=fixedImage)

region = fixedImage.GetLargestPossibleRegion()
resampler.SetSize(region.GetSize())
resampler.SetOutputOrigin(fixedImage.GetOrigin())
resampler.SetOutputSpacing(fixedImage.GetSpacing())
resampler.SetOutputDirection(fixedImage.GetDirection())
resampler.SetDefaultPixelValue(100)

######################## write the output ####################################
OutputPixelType = itk.F
OutputImageType = itk.Image[OutputPixelType, Dimension]

writer = itk.ImageFileWriter.New(Input=resampler, FileName=outputImageFile)
writer.SetFileName(outputImageFile)
writer.Update()

out_vis = resampler.GetOutput()


###############################################################################
########################### get the difference image ##########################
###############################################################################

difference = itk.SubtractImageFilter.New(Input1=fixedImage,Input2=resampler) #get the difference image

intensityRescaler = itk.RescaleIntensityImageFilter[FixedImageType,OutputImageType].New( #rescale the intensity
            Input=difference,
            OutputMinimum=itk.NumericTraits[OutputPixelType].min(),
            OutputMaximum=itk.NumericTraits[OutputPixelType].max())


after_vis = intensityRescaler.GetOutput() # Get output for plotting
resampler.SetDefaultPixelValue(1) # set default pixel value - set to 100 to see effect of translation

############ write the output #####################
writer.SetInput(intensityRescaler.GetOutput())
writer.SetFileName(differenceImageAfterFile)
writer.Update()

########### resampler params #########################
resampler2 = itk.ResampleImageFilter.New(Input=movingImage,Transform=identityTransform,UseReferenceImage=True,ReferenceImage=fixedImage)
difference2 = itk.SubtractImageFilter.New(Input1=fixedImage,Input2=resampler2)
intensityRescaler2 = itk.RescaleIntensityImageFilter[FixedImageType,OutputImageType].New(
            Input=difference2,
            OutputMinimum=itk.NumericTraits[OutputPixelType].min(),
            OutputMaximum=itk.NumericTraits[OutputPixelType].max())

before_vis = intensityRescaler2.GetOutput()
writer.SetInput(intensityRescaler2.GetOutput())
writer.SetFileName(differenceImageBeforeFile)
writer.Update()

## plot the optimization plot
plt.plot(iter,value)
plt.title("Optimization");
plt.xlabel("Iteration");
plt.ylabel("Metric");


sliced = 17
fig, ax = plt.subplots(1,5, figsize=(50,25))
ax[0].imshow(fixedImage[sliced], cmap='gray'), ax[0].set_title('Fixed Images',fontsize = 10)
ax[1].imshow(movingImage[sliced], cmap='gray'), ax[1].set_title('Moving Images',fontsize = 10)
ax[2].imshow(out_vis[sliced], cmap='gray'), ax[2].set_title('Output Images',fontsize = 10);
ax[3].imshow(before_vis[sliced], cmap='gray'), ax[3].set_title('Difference Before Image Registration',fontsize = 10);
ax[4].imshow(after_vis[sliced], cmap='gray'), ax[4].set_title('Difference After Image Registration',fontsize = 10);
