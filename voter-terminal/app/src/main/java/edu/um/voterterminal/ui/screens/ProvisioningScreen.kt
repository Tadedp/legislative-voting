package edu.um.voterterminal.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.Matrix
import android.util.Base64
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.ImageProxy
import androidx.camera.view.LifecycleCameraController
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import edu.um.voterterminal.R
import java.io.ByteArrayOutputStream

enum class ProvisioningStep {
    TOKEN_GATE,
    CAMERA_CAPTURE
}

@Composable
fun ProvisioningScreen(
    onProvisionClicked: (provisioningToken: String, biometricPayload: String) -> Unit,
    errorMessage: String? = null,
    onClearError: () -> Unit = {}
) {
    var step by remember { mutableStateOf(ProvisioningStep.TOKEN_GATE) }
    var provisioningToken by remember { mutableStateOf("") }

    LaunchedEffect(errorMessage) {
        if (errorMessage != null) {
            step = ProvisioningStep.TOKEN_GATE
            if (errorMessage.contains("Identity verification failed") || errorMessage.contains("token")) {
                provisioningToken = ""
            }
        }
    }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background
    ) {
        when (step) {
            ProvisioningStep.TOKEN_GATE -> {
                TokenGateStep(
                    provisioningToken = provisioningToken,
                    onTokenChange = { 
                        provisioningToken = it
                        onClearError()
                    },
                    errorMessage = errorMessage,
                    onProceed = {
                        if (provisioningToken.isNotBlank()) {
                            step = ProvisioningStep.CAMERA_CAPTURE
                        }
                    }
                )
            }
            ProvisioningStep.CAMERA_CAPTURE -> {
                CameraCaptureStep(
                    provisioningToken = provisioningToken,
                    onProvisionClicked = onProvisionClicked,
                    onBack = { step = ProvisioningStep.TOKEN_GATE }
                )
            }
        }
    }
}

@Composable
fun TokenGateStep(
    provisioningToken: String,
    onTokenChange: (String) -> Unit,
    errorMessage: String?,
    onProceed: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .systemBarsPadding()
            .padding(32.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text = stringResource(R.string.provisioning_title),
            style = MaterialTheme.typography.headlineMedium,
            color = MaterialTheme.colorScheme.primary,
            textAlign = TextAlign.Center
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = stringResource(R.string.provisioning_subtitle),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.7f),
            textAlign = TextAlign.Center
        )

        Spacer(modifier = Modifier.height(32.dp))

        OutlinedTextField(
            value = provisioningToken,
            onValueChange = onTokenChange,
            label = { Text(stringResource(R.string.provisioning_token_label)) },
            singleLine = true,
            modifier = Modifier.fillMaxWidth()
        )

        if (errorMessage != null) {
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = errorMessage,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
                textAlign = TextAlign.Center
            )
        }

        Spacer(modifier = Modifier.height(24.dp))

        Button(
            onClick = onProceed,
            enabled = provisioningToken.isNotBlank(),
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp)
        ) {
            Text(text = stringResource(R.string.proceed_facial_capture))
        }
    }
}

@Composable
fun CameraCaptureStep(
    provisioningToken: String,
    onProvisionClicked: (String, String) -> Unit,
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current

    var hasCameraPermission by remember { 
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
        ) 
    }

    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        hasCameraPermission = granted
    }

    LaunchedEffect(Unit) {
        if (!hasCameraPermission) {
            launcher.launch(Manifest.permission.CAMERA)
        }
    }

    if (hasCameraPermission) {
        val cameraController = remember {
            LifecycleCameraController(context).apply {
                cameraSelector = CameraSelector.DEFAULT_FRONT_CAMERA
                bindToLifecycle(lifecycleOwner)
            }
        }
        
        var isCapturing by remember { mutableStateOf(false) }

        Column(modifier = Modifier.fillMaxSize().systemBarsPadding()) {
            Box(modifier = Modifier.weight(1f).fillMaxWidth()) {
                AndroidView(
                    factory = { ctx ->
                        PreviewView(ctx).apply {
                            controller = cameraController
                            implementationMode = PreviewView.ImplementationMode.COMPATIBLE
                        }
                    },
                    modifier = Modifier.fillMaxSize()
                )
                
                if (isCapturing) {
                    CircularProgressIndicator(
                        modifier = Modifier.align(Alignment.Center)
                    )
                }
            }
            
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                TextButton(onClick = onBack, enabled = !isCapturing) {
                    Text(stringResource(R.string.back))
                }
                Button(
                    onClick = {
                        isCapturing = true
                        cameraController.takePicture(
                            ContextCompat.getMainExecutor(context),
                            object : ImageCapture.OnImageCapturedCallback() {
                                override fun onCaptureSuccess(image: ImageProxy) {
                                    try {
                                        val bitmap = image.toBitmap()
                                        val matrix = Matrix().apply { 
                                            postRotate(image.imageInfo.rotationDegrees.toFloat()) 
                                            preScale(-1f, 1f) // Mirror for front camera
                                        }
                                        val rotatedBitmap = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
                                        val baos = ByteArrayOutputStream()
                                        rotatedBitmap.compress(Bitmap.CompressFormat.JPEG, 80, baos)
                                        val base64String = Base64.encodeToString(baos.toByteArray(), Base64.NO_WRAP)
                                        
                                        onProvisionClicked(provisioningToken, base64String)
                                    } finally {
                                        image.close()
                                    }
                                }
                                override fun onError(exception: ImageCaptureException) {
                                    isCapturing = false
                                }
                            }
                        )
                    },
                    enabled = !isCapturing
                ) {
                    Text(stringResource(R.string.capture_provision))
                }
            }
        }
    } else {
        Column(
            modifier = Modifier.fillMaxSize().padding(32.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                stringResource(R.string.camera_permission_required),
                textAlign = TextAlign.Center
            )
            Spacer(modifier = Modifier.height(16.dp))
            Button(onClick = { launcher.launch(Manifest.permission.CAMERA) }) {
                Text(stringResource(R.string.grant_permission))
            }
            Spacer(modifier = Modifier.height(8.dp))
            TextButton(onClick = onBack) {
                Text(stringResource(R.string.back))
            }
        }
    }
}
